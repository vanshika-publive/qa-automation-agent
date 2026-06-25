import json
import math
import os
import threading
import uuid
from pathlib import Path

from core.constants import PaginationDefaults, ExecutionStatus
from core.models import Collection, Test, Environment, Execution, ExecutionStep
from pipeline.constants import ERROR_TRUNCATE_LENGTH
from utils.datetime_utils import DateTimeUtils
from utils.slug import to_collection_slug


class ExecutionService:

    @staticmethod
    def list_with_filters(params: dict) -> tuple:
        try:
            page = max(1, int(params.get('page', PaginationDefaults.PAGE)))
        except (ValueError, TypeError):
            page = PaginationDefaults.PAGE
        try:
            page_size = min(
                PaginationDefaults.MAX_PAGE_SIZE,
                max(1, int(params.get('pageSize', PaginationDefaults.PAGE_SIZE))),
            )
        except (ValueError, TypeError):
            page_size = PaginationDefaults.PAGE_SIZE

        # Build the filtered base queryset WITHOUT the window annotation.
        # count() must run before with_run_number() — PostgreSQL forbids aggregating
        # over a Window expression at the same query level.
        qs = Execution.objects.with_related()

        if params.get('testId'):
            qs = qs.for_test(params['testId'])
        collection_id = params.get('collection_id') or params.get('collectionId')
        if collection_id:
            qs = qs.for_collection(collection_id)
        if params.get('status'):
            qs = qs.with_status(params['status'])
        qs = qs.in_date_range(params.get('from'), params.get('to'))

        total = qs.count()
        offset = (page - 1) * page_size
        # Add the window annotation only for the actual data slice.
        rows = qs.with_run_number().order_by('-started_at')[offset:offset + page_size]

        pagination = {
            'page': page,
            'pageSize': page_size,
            'total': total,
            'totalPages': math.ceil(total / page_size) if total > 0 else 0,
        }
        # Rows are serialized by ExecutionListSerializer in the view.
        return rows, pagination

    @staticmethod
    def get_detail(execution_id: str) -> tuple:
        execution = Execution.objects.with_related().get(id=execution_id)
        steps = list(
            ExecutionStep.all_objects.filter(execution_id=execution_id).order_by('started_at')
        )
        run_number = Execution.objects.filter(
            test_id=execution.test_id,
            started_at__lte=execution.started_at,
            deleted_at__isnull=True,
        ).count()
        return execution, steps, run_number

    @staticmethod
    def soft_delete(execution_id: str) -> None:
        execution = Execution.objects.get(id=execution_id)
        if execution.is_running:
            raise PermissionError('Cannot delete a running execution')
        execution.deleted_at = DateTimeUtils.now_iso()
        execution.save()

    @staticmethod
    def parse_results_json(report_dir: str, project_root: str):
        if not report_dir:
            return None
        results_path = os.path.join(project_root, 'reports', report_dir, 'results.json')
        if not os.path.isfile(results_path):
            return None
        try:
            report = json.loads(Path(results_path).read_text(encoding='utf-8'))
            results = []
            ExecutionService._flatten_suites(report.get('suites', []), results)
            return results
        except Exception:
            return None

    @staticmethod
    def results_as_steps(report_dir: str, project_root: str) -> list:
        """Per-test results reshaped into the snake_case `/steps` endpoint contract."""
        results = ExecutionService.parse_results_json(report_dir, project_root) or []
        return [
            {
                'id': str(i),
                'test_name': r['title'],
                'status': r['status'],
                'duration_ms': r['durationMs'],
                'error_message': r['error'],
            }
            for i, r in enumerate(results)
        ]

    @staticmethod
    def _flatten_suites(suites: list, results: list, file: str = '') -> None:
        for suite in suites:
            current_file = suite.get('file', file)
            if 'suites' in suite:
                ExecutionService._flatten_suites(suite['suites'], results, current_file)
            for spec in suite.get('specs', []):
                test = (spec.get('tests') or [{}])[0] if spec.get('tests') else {}
                test_results = test.get('results', [{}])
                first_result = test_results[0] if test_results else {}
                raw_status = (
                    first_result.get('status')
                    or test.get('status')
                    or ('expected' if spec.get('ok') else 'unexpected')
                )
                if raw_status in ('expected', 'passed'):
                    s = 'passed'
                elif raw_status == 'skipped':
                    s = 'skipped'
                else:
                    s = 'failed'
                duration_ms = first_result.get('duration') or test.get('duration', 0)
                errors = first_result.get('errors') or test.get('errors', [])
                err_msg = errors[0].get('message', '') if errors else None
                if err_msg:
                    err_msg = err_msg[:ERROR_TRUNCATE_LENGTH]
                results.append({
                    'title': spec.get('title', 'Unnamed test'),
                    'file': os.path.basename(current_file) if current_file else '',
                    'status': s,
                    'durationMs': duration_ms,
                    'error': err_msg,
                })

    @staticmethod
    def create_execution(test_id: str, environment_id: str) -> str:
        execution_id = str(uuid.uuid4())
        Execution.all_objects.create(
            id=execution_id,
            test_id=test_id,
            environment_id=environment_id,
            status=ExecutionStatus.RUNNING,
            started_at=DateTimeUtils.now_iso(),
        )
        return execution_id

    @staticmethod
    def launch_pipeline(execution_id: str, test_id: str, environment_id: str) -> None:
        def _run():
            import django
            django.setup()
            from pipeline.run_pipeline import PipelineRunner
            PipelineRunner.run(execution_id, test_id, environment_id)
        threading.Thread(target=_run, daemon=True).start()

    @staticmethod
    def launch_spec_run(execution_id: str, test_id: str, spec_filename: str, environment_id: str) -> None:
        def _run():
            import django
            django.setup()
            from pipeline.run_pipeline import PipelineRunner
            PipelineRunner.run_spec(execution_id, test_id, spec_filename, environment_id)
        threading.Thread(target=_run, daemon=True).start()

    @staticmethod
    def launch_all_specs(collection_id: str, environment_id: str) -> str:
        from django.conf import settings
        first_test = Test.objects.filter(collection_id=collection_id).order_by('created_at').first()
        if not first_test:
            raise LookupError('No tests in this collection')
        collection = Collection.objects.get(id=collection_id)
        slug = to_collection_slug(collection.name)
        specs_dir = os.path.join(settings.PLAYWRIGHT_PROJECT_ROOT, 'tests', slug)
        if not os.path.isdir(specs_dir):
            raise FileNotFoundError(f'No spec directory at tests/{slug}')
        execution_id = ExecutionService.create_execution(first_test.id, environment_id)
        ExecutionService.launch_spec_run(execution_id, first_test.id, slug, environment_id)
        return execution_id

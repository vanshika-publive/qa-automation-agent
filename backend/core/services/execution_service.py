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
from utils.failure_classifier import classify_failure
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
        if params.get('search'):
            qs = qs.search_by_name(params['search'])
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
        except Exception:
            return None
        results = []
        ExecutionService._collect_pytest_results(report.get('tests', []), results)
        return results

    @staticmethod
    def failure_summary(report_dir: str, project_root: str):
        """Classified reason for an execution's failure, from the first failed test.

        Returns {category, summary, locator} or None when nothing failed / no results.
        """
        results = ExecutionService.parse_results_json(report_dir, project_root) or []
        first_failed = next(
            (r for r in results if r['status'] == 'failed' and r.get('error')), None
        )
        if not first_failed:
            return None
        return classify_failure(first_failed['error'])

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
    def _collect_pytest_results(tests: list, results: list) -> None:
        """Read pytest-json-report `tests[]` into the /tests output contract.

        results.json is written by pytest-json-report — schema is `tests[]`, each with
        setup/call/teardown phases — NOT a Playwright `suites` report. Reading it as the
        latter (the old `_flatten_suites`) silently returned nothing, so the UI showed
        "No results" and the actual failure never reached the page. Read the phase that
        actually failed so the locator/stack trace surfaces.
        """
        for item in tests:
            nodeid = item.get('nodeid', '')
            outcome = item.get('outcome', '')
            if outcome == 'passed':
                status_value = 'passed'
            elif outcome in ('skipped', 'xfailed', 'xpassed'):
                status_value = 'skipped'
            else:
                status_value = 'failed'

            phases = [item.get('setup'), item.get('call'), item.get('teardown')]
            failing_phase = next(
                (p for p in phases if p and p.get('outcome') not in (None, 'passed')),
                item.get('call') or {},
            )

            error = None
            if status_value == 'failed':
                error = ExecutionService._phase_error_text(failing_phase)

            call = item.get('call') or {}
            duration_s = call.get('duration')
            if duration_s is None:
                duration_s = sum((p or {}).get('duration', 0) for p in phases)

            results.append({
                'title': nodeid.split('::')[-1] if nodeid else 'Unnamed test',
                'file': os.path.basename(nodeid.split('::')[0]) if nodeid else '',
                'status': status_value,
                'durationMs': int((duration_s or 0) * 1000),
                'error': error,
            })

    @staticmethod
    def _phase_error_text(phase: dict):
        """Concise failure text from a pytest phase: prefer the exception message
        (`crash.message`, e.g. 'TimeoutError: ... waiting for locator(...)') over the
        verbose source-included longrepr."""
        crash = phase.get('crash') or {}
        longrepr = phase.get('longrepr')
        if isinstance(longrepr, dict):
            longrepr = (
                longrepr.get('longrepr')
                or longrepr.get('reprcrash', {}).get('message', '')
            )
        msg = crash.get('message') or longrepr or 'Unknown error'
        if not isinstance(msg, str):
            msg = str(msg)
        return msg[:ERROR_TRUNCATE_LENGTH]

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

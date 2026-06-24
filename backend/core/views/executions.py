import json
import math
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from django.db.models import F, Window
from django.db.models.functions import RowNumber
from django.http import StreamingHttpResponse
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.views import APIView
from rest_framework.response import Response

from core.models import Collection, Test, Environment, Execution, ExecutionStep
from core.views.tests import _find_spec_file
from utils.slug import to_collection_slug

PROJECT_ROOT = settings.PLAYWRIGHT_PROJECT_ROOT
DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
SSE_POLL_INTERVAL = 0.8
ERROR_TRUNCATE_LENGTH = 400


def _now_iso():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def _serialize_execution(e):
    return {
        'id': e['id'] if isinstance(e, dict) else e.id,
        'testId': e.get('test_id', '') if isinstance(e, dict) else e.test_id,
        'environmentId': e.get('environment_id', '') if isinstance(e, dict) else e.environment_id,
        'status': e.get('status', '') if isinstance(e, dict) else e.status,
        'startedAt': e.get('started_at', '') if isinstance(e, dict) else e.started_at,
        'completedAt': e.get('completed_at') if isinstance(e, dict) else e.completed_at,
        'durationMs': e.get('duration_ms') if isinstance(e, dict) else e.duration_ms,
        'passCount': e.get('pass_count', 0) if isinstance(e, dict) else e.pass_count,
        'failCount': e.get('fail_count', 0) if isinstance(e, dict) else e.fail_count,
        'totalCount': e.get('total_count', 0) if isinstance(e, dict) else e.total_count,
        'reportDir': e.get('report_dir') if isinstance(e, dict) else e.report_dir,
    }


def _serialize_step(s):
    return {
        'id': s['id'] if isinstance(s, dict) else s.id,
        'executionId': s.get('execution_id', '') if isinstance(s, dict) else s.execution_id,
        'stepName': s.get('step_name', '') if isinstance(s, dict) else s.step_name,
        'status': s.get('status', '') if isinstance(s, dict) else s.status,
        'log': s.get('log', '') if isinstance(s, dict) else s.log,
        'startedAt': s.get('started_at', '') if isinstance(s, dict) else s.started_at,
        'completedAt': s.get('completed_at') if isinstance(s, dict) else s.completed_at,
    }


def _parse_results_json(report_dir):
    if not report_dir:
        return None
    results_path = os.path.join(PROJECT_ROOT, 'reports', report_dir, 'results.json')
    if not os.path.isfile(results_path):
        return None
    try:
        report = json.loads(Path(results_path).read_text(encoding='utf-8'))
        results = []
        _flatten_suites(report.get('suites', []), results)
        return results
    except Exception:
        return None


def _flatten_suites(suites, results, file=''):
    for suite in suites:
        current_file = suite.get('file', file)
        if 'suites' in suite:
            _flatten_suites(suite['suites'], results, current_file)
        for spec in suite.get('specs', []):
            test = (spec.get('tests') or [{}])[0] if spec.get('tests') else {}
            test_results = test.get('results', [{}])
            first_result = test_results[0] if test_results else {}

            raw_status = first_result.get('status') or test.get('status') or ('expected' if spec.get('ok') else 'unexpected')
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


# --- Execution list with filters + pagination ---

class ExecutionList(APIView):
    def get(self, request):
        q = request.query_params
        test_id = q.get('testId')
        collection_id = q.get('collection_id') or q.get('collectionId')
        status_filter = q.get('status')
        from_date = q.get('from')
        to_date = q.get('to')

        try:
            page = max(1, int(q.get('page', DEFAULT_PAGE)))
        except (ValueError, TypeError):
            page = DEFAULT_PAGE
        try:
            page_size = min(MAX_PAGE_SIZE, max(1, int(q.get('pageSize', DEFAULT_PAGE_SIZE))))
        except (ValueError, TypeError):
            page_size = DEFAULT_PAGE_SIZE

        qs = Execution.objects.filter(deleted_at__isnull=True)

        if test_id:
            qs = qs.filter(test_id=test_id)
        if collection_id:
            qs = qs.filter(test__collection_id=collection_id)
        if status_filter:
            qs = qs.filter(status=status_filter)
        if from_date:
            qs = qs.filter(started_at__gte=f'{from_date}T00:00:00.000Z')
        if to_date:
            qs = qs.filter(started_at__lte=f'{to_date}T23:59:59.999Z')

        total = qs.count()
        total_pages = math.ceil(total / page_size) if total > 0 else 0
        offset = (page - 1) * page_size

        executions = (
            qs.select_related('test', 'test__collection', 'environment')
            .annotate(
                run_number=Window(
                    expression=RowNumber(),
                    partition_by=F('test_id'),
                    order_by=F('started_at').asc(),
                )
            )
            .order_by('-started_at')[offset:offset + page_size]
        )

        data = []
        for e in executions:
            data.append({
                'id': e.id,
                'testId': e.test_id,
                'collectionId': e.test.collection_id,
                'collectionName': e.test.collection.name,
                'environmentId': e.environment_id,
                'status': e.status,
                'startedAt': e.started_at,
                'completedAt': e.completed_at,
                'durationMs': e.duration_ms,
                'passCount': e.pass_count,
                'failCount': e.fail_count,
                'totalCount': e.total_count,
                'reportDir': e.report_dir,
                'testName': e.test.name,
                'environmentName': e.environment.name,
                'environmentUrl': e.environment.base_url,
                'runNumber': e.run_number,
            })

        return Response({
            'data': data,
            'pagination': {
                'page': page,
                'pageSize': page_size,
                'total': total,
                'totalPages': total_pages,
            },
        })


class ExecutionDetail(APIView):
    def get(self, request, id):
        try:
            e = Execution.objects.select_related('test', 'test__collection', 'environment').get(id=id)
        except Execution.DoesNotExist:
            return Response({'error': 'Execution not found'}, status=status.HTTP_404_NOT_FOUND)

        steps = ExecutionStep.all_objects.filter(execution_id=id).order_by('started_at')
        step_data = [_serialize_step(s) for s in steps]

        run_number = Execution.objects.filter(
            test_id=e.test_id,
            started_at__lte=e.started_at,
            deleted_at__isnull=True,
        ).count()

        data = {
            'id': e.id,
            'testId': e.test_id,
            'collectionId': e.test.collection_id,
            'collectionName': e.test.collection.name,
            'environmentId': e.environment_id,
            'status': e.status,
            'startedAt': e.started_at,
            'completedAt': e.completed_at,
            'durationMs': e.duration_ms,
            'passCount': e.pass_count,
            'failCount': e.fail_count,
            'totalCount': e.total_count,
            'reportDir': e.report_dir,
            'testName': e.test.name,
            'environmentName': e.environment.name,
            'environmentUrl': e.environment.base_url,
            'runNumber': run_number,
            'steps': step_data,
        }
        return Response(data)

    def delete(self, request, id):
        try:
            e = Execution.objects.get(id=id)
        except Execution.DoesNotExist:
            return Response({'error': 'Execution not found'}, status=status.HTTP_404_NOT_FOUND)

        if e.status == 'running':
            return Response(
                {'error': 'Cannot delete a running execution'},
                status=status.HTTP_409_CONFLICT,
            )

        e.deleted_at = _now_iso()
        e.save()
        return Response({'id': id})


@api_view(['GET'])
def execution_steps(request, id):
    try:
        e = Execution.objects.get(id=id)
    except Execution.DoesNotExist:
        return Response({'error': 'Execution not found'}, status=status.HTTP_404_NOT_FOUND)

    if not e.report_dir:
        return Response({
            'data': [],
            'pending': e.status == 'running',
            'error': None,
        })

    results = _parse_results_json(e.report_dir)
    steps = [
        {
            'id': str(i),
            'test_name': r['title'],
            'status': r['status'],
            'duration_ms': r['durationMs'],
            'error_message': r['error'],
        }
        for i, r in enumerate(results or [])
    ]
    return Response({
        'data': steps,
        'pending': False,
        'error': None,
    })


@api_view(['GET'])
def execution_tests(request, id):
    try:
        e = Execution.objects.get(id=id)
    except Execution.DoesNotExist:
        return Response({'error': 'Execution not found'}, status=status.HTTP_404_NOT_FOUND)

    if not e.report_dir:
        return Response({
            'data': [],
            'pending': e.status == 'running',
            'error': None,
        })

    results = _parse_results_json(e.report_dir)
    return Response({
        'data': results or [],
        'pending': e.status == 'running',
        'error': None,
    })


@api_view(['GET'])
def execution_files(request, id):
    try:
        e = Execution.objects.select_related('test', 'test__collection').get(id=id)
    except Execution.DoesNotExist:
        return Response({'error': 'Execution not found'}, status=status.HTTP_404_NOT_FOUND)

    slug = to_collection_slug(e.test.collection.name)
    tests_root = os.path.join(PROJECT_ROOT, 'tests')
    specs_root = os.path.join(PROJECT_ROOT, 'specs')

    abs_path = _find_spec_file(e.test.name, slug, tests_root)
    spec_filename = None
    spec_content = None
    if abs_path:
        spec_filename = os.path.relpath(abs_path, tests_root).replace('\\', '/')
        try:
            spec_content = Path(abs_path).read_text(encoding='utf-8')
        except Exception:
            pass

    plan_path = os.path.join(specs_root, slug, str(e.test_id), 'plan.md')
    plan_content = None
    if os.path.isfile(plan_path):
        try:
            plan_content = Path(plan_path).read_text(encoding='utf-8')
        except Exception:
            pass

    return Response({
        'specFilename': spec_filename,
        'specContent': spec_content,
        'planContent': plan_content,
    })


# --- SSE Streaming ---

def execution_stream(request, id):
    def event_stream():
        while True:
            try:
                e = Execution.all_objects.filter(id=id).first()
                steps = list(
                    ExecutionStep.all_objects
                    .filter(execution_id=id)
                    .order_by('started_at')
                )

                execution_data = _serialize_execution(e) if e else None
                steps_data = [_serialize_step(s) for s in steps]

                payload = json.dumps({'execution': execution_data, 'steps': steps_data})
                yield f'data: {payload}\n\n'

                if not e or e.status != 'running':
                    break

                time.sleep(SSE_POLL_INTERVAL)
            except Exception:
                break

    response = StreamingHttpResponse(
        event_stream(),
        content_type='text/event-stream',
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response


# --- Run endpoints ---

@api_view(['POST'])
def run_test(request, test_id):
    environment_id = (request.data.get('environmentId') or '').strip()
    if not environment_id:
        return Response({'error': 'environmentId is required'}, status=status.HTTP_400_BAD_REQUEST)

    if not Test.objects.filter(id=test_id).exists():
        return Response({'error': 'Test not found'}, status=status.HTTP_404_NOT_FOUND)

    if not Environment.objects.filter(id=environment_id).exists():
        return Response({'error': 'Environment not found'}, status=status.HTTP_404_NOT_FOUND)

    execution_id = str(uuid.uuid4())
    now = _now_iso()
    Execution.all_objects.create(
        id=execution_id,
        test_id=test_id,
        environment_id=environment_id,
        status='running',
        started_at=now,
    )

    def _run():
        import django
        django.setup()
        from pipeline.run_pipeline import run_pipeline
        run_pipeline(execution_id, test_id, environment_id)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    return Response({'executionId': execution_id}, status=status.HTTP_202_ACCEPTED)


@api_view(['POST'])
def run_all_specs(request, collection_id):
    environment_id = (request.data.get('environmentId') or '').strip()
    if not environment_id:
        return Response({'error': 'environmentId is required'}, status=status.HTTP_400_BAD_REQUEST)

    first_test = (
        Test.objects
        .filter(collection_id=collection_id)
        .order_by('created_at')
        .first()
    )
    if not first_test:
        return Response({'error': 'No tests in this collection'}, status=status.HTTP_404_NOT_FOUND)

    try:
        collection = Collection.objects.get(id=collection_id)
    except Collection.DoesNotExist:
        return Response({'error': 'Collection not found'}, status=status.HTTP_404_NOT_FOUND)

    slug = to_collection_slug(collection.name)
    specs_dir = os.path.join(PROJECT_ROOT, 'tests', slug)
    if not os.path.isdir(specs_dir):
        return Response(
            {'error': f'No spec directory at tests/{slug}'},
            status=status.HTTP_404_NOT_FOUND,
        )

    execution_id = str(uuid.uuid4())
    now = _now_iso()
    Execution.all_objects.create(
        id=execution_id,
        test_id=first_test.id,
        environment_id=environment_id,
        status='running',
        started_at=now,
    )

    def _run():
        import django
        django.setup()
        from pipeline.run_pipeline import run_spec_file
        run_spec_file(execution_id, first_test.id, slug, environment_id)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    return Response({'executionId': execution_id}, status=status.HTTP_202_ACCEPTED)

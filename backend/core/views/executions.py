import json
import os
import time
from pathlib import Path

from django.conf import settings
from django.http import StreamingHttpResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.constants import SSEConstants
from core.decorators import fetch_object
from core.models import Execution, ExecutionStep
from core.renderers import EventStreamRenderer
from core.serializers import (
    ExecutionSerializer,
    ExecutionListSerializer,
    ExecutionDetailSerializer,
    ExecutionStepSerializer,
)
from core.services.artifact_store import ArtifactStore
from core.services.execution_service import ExecutionService
from core.services.test_service import TestService
from utils.slug import to_collection_slug

PROJECT_ROOT = settings.PLAYWRIGHT_PROJECT_ROOT


class ExecutionListView(APIView):
    """/executions"""

    def get(self, request):
        rows, pagination = ExecutionService.list_with_filters(request.query_params)
        return Response({
            'data': ExecutionListSerializer(rows, many=True).data,
            'pagination': pagination,
        })


class ExecutionDetailView(APIView):
    """/executions/<pk>"""

    def get(self, request, pk=None):
        try:
            execution, steps, run_number = ExecutionService.get_detail(pk)
        except Execution.DoesNotExist:
            return Response({'error': 'Execution not found'}, status=status.HTTP_404_NOT_FOUND)
        failure = None
        if execution.status == 'failed' and execution.report_dir:
            failure = ExecutionService.failure_summary(execution.report_dir, PROJECT_ROOT)
        return Response(
            ExecutionDetailSerializer(
                execution,
                context={'run_number': run_number, 'steps': steps, 'failure': failure},
            ).data
        )

    def delete(self, request, pk=None):
        try:
            ExecutionService.soft_delete(pk)
        except Execution.DoesNotExist:
            return Response({'error': 'Execution not found'}, status=status.HTTP_404_NOT_FOUND)
        except PermissionError as e:
            return Response({'error': str(e)}, status=status.HTTP_409_CONFLICT)
        return Response({'id': pk})


class ExecutionStopView(APIView):
    """/executions/<pk>/stop"""

    def post(self, request, pk=None):
        try:
            ExecutionService.request_stop(pk)
        except Execution.DoesNotExist:
            return Response({'error': 'Execution not found'}, status=status.HTTP_404_NOT_FOUND)
        except PermissionError as e:
            return Response({'error': str(e)}, status=status.HTTP_409_CONFLICT)
        return Response({'id': pk})


class ExecutionStepsView(APIView):
    """/executions/<pk>/steps"""

    @fetch_object(Execution, 'Execution not found')
    def get(self, request, obj=None, pk=None):
        if not obj.report_dir:
            return Response({'data': [], 'pending': obj.is_running, 'error': None})
        steps = ExecutionService.results_as_steps(obj.report_dir, PROJECT_ROOT)
        return Response({'data': steps, 'pending': False, 'error': None})


class ExecutionTestsView(APIView):
    """/executions/<pk>/tests"""

    @fetch_object(Execution, 'Execution not found')
    def get(self, request, obj=None, pk=None):
        if not obj.report_dir:
            return Response({'data': [], 'pending': obj.is_running, 'error': None})
        results = ExecutionService.parse_results_json(obj.report_dir, PROJECT_ROOT)
        return Response({'data': results or [], 'pending': obj.is_running, 'error': None})


class ExecutionFilesView(APIView):
    """/executions/<pk>/files"""

    @fetch_object(Execution, 'Execution not found', select_related=('test', 'test__collection'))
    def get(self, request, obj=None, pk=None):
        slug = to_collection_slug(obj.test.collection.name)
        tests_root = os.path.join(PROJECT_ROOT, 'tests')
        specs_root = os.path.join(PROJECT_ROOT, 'specs')
        spec_filename = spec_content = None
        # Source of truth is the DB; fall back to disk for un-mirrored/legacy runs.
        spec_row = ArtifactStore.resolve_spec_for_test(obj.test)
        if spec_row:
            spec_filename = f'{slug}/{spec_row.filename}'
            spec_content = spec_row.content
        else:
            abs_path = TestService.resolve_spec_file(obj.test, slug, tests_root)
            if abs_path:
                spec_filename = os.path.relpath(abs_path, tests_root).replace('\\', '/')
                try:
                    spec_content = Path(abs_path).read_text(encoding='utf-8')
                except Exception:
                    pass
        plan_content = ArtifactStore.get_plan_md(obj.test_id)
        if plan_content is None:
            plan_path = os.path.join(specs_root, slug, str(obj.test_id), 'plan.md')
            if os.path.isfile(plan_path):
                try:
                    plan_content = Path(plan_path).read_text(encoding='utf-8')
                except Exception:
                    pass
        screenshots = ExecutionService.list_screenshots(obj.report_dir, PROJECT_ROOT)
        return Response({
            'specFilename': spec_filename,
            'specContent': spec_content,
            'planContent': plan_content,
            'screenshots': screenshots,
        })


class ExecutionStreamView(APIView):
    """/executions/<pk>/stream — Server-Sent Events"""

    renderer_classes = [EventStreamRenderer]

    def get(self, request, pk=None):
        def _event_stream():
            while True:
                try:
                    execution = Execution.all_objects.filter(id=pk).first()
                    steps = list(
                        ExecutionStep.all_objects.filter(execution_id=pk).order_by('started_at')
                    )
                    payload = json.dumps({
                        'execution': ExecutionSerializer(execution).data if execution else None,
                        'steps': ExecutionStepSerializer(steps, many=True).data,
                    })
                    yield f'data: {payload}\n\n'
                    if not execution or not execution.is_running:
                        break
                    time.sleep(SSEConstants.POLL_INTERVAL_S)
                except Exception:
                    break

        response = StreamingHttpResponse(_event_stream(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response

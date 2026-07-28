import os

from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.decorators import validate_body, fetch_object
from core.models import Test, Environment
from core.serializers import (
    TestSerializer,
    TestUpdateSerializer,
    SpecSaveSerializer,
    RunSerializer,
    RunSpecSerializer,
)
from core.services.artifact_store import ArtifactStore
from core.services.execution_service import ExecutionService
from core.services.test_service import TestService
from utils.datetime_utils import DateTimeUtils
from utils.slug import to_collection_slug

PROJECT_ROOT = settings.PLAYWRIGHT_PROJECT_ROOT


class TestDetailView(APIView):
    """/tests/<pk>"""

    @fetch_object(Test, 'Test not found')
    @validate_body(TestUpdateSerializer)
    def put(self, request, obj=None, data=None, pk=None):
        TestService.update(obj, data)
        return Response(TestSerializer(obj).data)

    def delete(self, request, pk=None):
        if not TestService.soft_delete(pk):
            return Response({'error': 'Test not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'id': pk})


class TestSpecView(APIView):
    """/tests/<pk>/spec"""

    @fetch_object(Test, 'Test not found', select_related=('collection',))
    def get(self, request, obj=None, pk=None):
        slug = to_collection_slug(obj.collection.name)
        tests_root = os.path.join(PROJECT_ROOT, 'tests')
        # Source of truth is the DB; fall back to disk for tests not yet mirrored/backfilled.
        spec_row = ArtifactStore.resolve_spec_for_test(obj)
        if spec_row:
            return Response({
                'filename': f'{slug}/{spec_row.filename}',
                'content': spec_row.content,
                'lastModified': spec_row.updated_at,
            })
        abs_path = TestService.resolve_spec_file(obj, slug, tests_root)
        if not abs_path:
            return Response({
                'data': {'filename': None, 'content': None, 'lastModified': None},
                'error': 'No spec file generated yet for this test',
            })
        return Response(TestService.read_spec_file(abs_path, tests_root))

    @fetch_object(Test, 'Test not found')
    @validate_body(SpecSaveSerializer)
    def put(self, request, obj=None, data=None, pk=None):
        # Persist to the DB (canonical) and mirror to disk so an in-flight run still sees the edit.
        ArtifactStore.save_spec(obj.id, data['filename'], data['content'])
        TestService.write_spec_file(data['filename'], data['content'], os.path.join(PROJECT_ROOT, 'tests'))
        return Response({'ok': True, 'filename': data['filename'], 'savedAt': DateTimeUtils.now_iso()})


class TestRunSpecView(APIView):
    """/tests/<pk>/run-spec"""

    @validate_body(RunSpecSerializer)
    @fetch_object(Test, 'Test not found')
    def post(self, request, obj=None, data=None, pk=None):
        execution_id = ExecutionService.create_execution(obj.id, data['environmentId'])
        ExecutionService.launch_spec_run(execution_id, obj.id, data['filename'], data['environmentId'])
        return Response({'executionId': execution_id}, status=status.HTTP_202_ACCEPTED)


class TestRunView(APIView):
    """/tests/<pk>/run  (also /executions/tests/<pk>/run)"""

    @validate_body(RunSerializer)
    @fetch_object(Test, 'Test not found')
    def post(self, request, obj=None, data=None, pk=None):
        environment_id = data['environmentId']
        if not Environment.objects.filter(id=environment_id).exists():
            return Response({'error': 'Environment not found'}, status=status.HTTP_404_NOT_FOUND)
        execution_id = ExecutionService.create_execution(obj.id, environment_id)
        ExecutionService.launch_pipeline(execution_id, obj.id, environment_id)
        return Response({'executionId': execution_id}, status=status.HTTP_202_ACCEPTED)


class SpecReadView(APIView):
    """/specs/view?file=<path> — read a generated spec file's contents."""

    def get(self, request):
        file_path = request.query_params.get('file', '')
        if not file_path or '..' in file_path:
            return Response({'error': 'Invalid file path'}, status=status.HTTP_400_BAD_REQUEST)
        tests_root = os.path.join(PROJECT_ROOT, 'tests')
        # DB (source of truth) first: resolve <slug>/<basename> back to a spec row.
        slug = file_path.split('/')[0]
        collection_id = TestService.collection_id_for_slug(slug)
        if collection_id:
            row = ArtifactStore.get_spec_in_collection(collection_id, file_path)
            if row:
                return Response({'content': row.content})
        if not os.path.isfile(os.path.join(tests_root, file_path)):
            return Response({'error': 'File not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'content': TestService.read_raw_spec(file_path, tests_root)})


class SpecDeleteView(APIView):
    """/specs?file=<path> — delete a generated spec file."""

    def delete(self, request):
        file_path = request.query_params.get('file', '')
        if not file_path or '..' in file_path:
            return Response({'error': 'Invalid file path'}, status=status.HTTP_400_BAD_REQUEST)
        tests_root = os.path.join(PROJECT_ROOT, 'tests')
        # Soft-delete the canonical DB row; also remove the on-disk scratch copy if present.
        slug = file_path.split('/')[0]
        collection_id = TestService.collection_id_for_slug(slug)
        deleted_in_db = 0
        if collection_id:
            deleted_in_db = ArtifactStore.delete_spec_in_collection(collection_id, file_path)
        on_disk = os.path.isfile(os.path.join(tests_root, file_path))
        if not deleted_in_db and not on_disk:
            return Response({'error': 'File not found'}, status=status.HTTP_404_NOT_FOUND)
        if on_disk:
            TestService.delete_spec_file(file_path, tests_root)
        return Response({'deleted': file_path})

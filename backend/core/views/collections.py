import os

from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.decorators import validate_body, fetch_object
from core.models import Collection
from core.serializers import (
    CollectionSerializer,
    CollectionWriteSerializer,
    TestSerializer,
    TestCreateSerializer,
    RunSerializer,
)
from core.services.collection_service import CollectionService
from core.services.execution_service import ExecutionService
from core.services.test_service import TestService
from utils.slug import to_collection_slug

PROJECT_ROOT = settings.PLAYWRIGHT_PROJECT_ROOT


class CollectionListView(APIView):
    """/collections"""

    def get(self, request):
        collections = CollectionService.list_all()
        return Response(CollectionSerializer(collections, many=True).data)

    @validate_body(CollectionWriteSerializer)
    def post(self, request, data=None):
        collection = CollectionService.create(data['name'])
        return Response(CollectionSerializer(collection).data, status=status.HTTP_201_CREATED)


class CollectionDetailView(APIView):
    """/collections/<pk>"""

    @validate_body(CollectionWriteSerializer)
    def patch(self, request, data=None, pk=None):
        name = data['name']
        if not CollectionService.rename(pk, name):
            return Response({'error': 'Collection not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'id': pk, 'name': name})

    def delete(self, request, pk=None):
        if not CollectionService.soft_delete(pk):
            return Response({'error': 'Collection not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'id': pk})


class CollectionTestsView(APIView):
    """/collections/<pk>/tests"""

    @fetch_object(Collection, 'Collection not found')
    def get(self, request, obj=None, pk=None):
        return Response(TestService.list_by_collection(obj.id, PROJECT_ROOT))

    @fetch_object(Collection, 'Collection not found')
    @validate_body(TestCreateSerializer)
    def post(self, request, obj=None, data=None, pk=None):
        test = TestService.create(obj.id, data['name'], data['prompt'])
        return Response(TestSerializer(test).data, status=status.HTTP_201_CREATED)


class CollectionSpecsView(APIView):
    """/collections/<pk>/specs"""

    @fetch_object(Collection, 'Collection not found')
    def get(self, request, obj=None, pk=None):
        slug = to_collection_slug(obj.name)
        return Response(
            TestService.list_specs_by_collection(obj.id, slug, os.path.join(PROJECT_ROOT, 'tests'))
        )


class CollectionRunSpecsView(APIView):
    """/collections/<pk>/run-all-specs"""

    @validate_body(RunSerializer)
    def post(self, request, data=None, pk=None):
        try:
            execution_id = ExecutionService.launch_all_specs(pk, data['environmentId'])
        except (LookupError, FileNotFoundError) as e:
            return Response({'error': str(e)}, status=status.HTTP_404_NOT_FOUND)
        return Response({'executionId': execution_id}, status=status.HTTP_202_ACCEPTED)

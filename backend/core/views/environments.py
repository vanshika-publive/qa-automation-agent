import os

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.decorators import validate_body, fetch_object
from core.models import Environment
from core.serializers import (
    EnvironmentSerializer,
    EnvironmentCreateSerializer,
    EnvironmentUpdateSerializer,
)
from core.services.environment_service import EnvironmentService


class EnvironmentListView(APIView):
    """/environments"""

    def get(self, request):
        return Response(EnvironmentSerializer(EnvironmentService.list_all(), many=True).data)

    @validate_body(EnvironmentCreateSerializer)
    def post(self, request, data=None):
        environment = EnvironmentService.create(
            name=data['name'],
            base_url=data['baseUrl'],
            login_email=data['loginEmail'],
            login_password=data['loginPassword'],
            description=data['description'],
            is_active=data['isActive'],
        )
        return Response(EnvironmentSerializer(environment).data, status=status.HTTP_201_CREATED)


class EnvironmentDetailView(APIView):
    """/environments/<pk>"""

    @fetch_object(Environment, 'Environment not found')
    @validate_body(EnvironmentUpdateSerializer)
    def put(self, request, obj=None, data=None, pk=None):
        EnvironmentService.update(
            obj,
            name=data.get('name'),
            base_url=data.get('baseUrl'),
            description=data.get('description'),
            is_active=data.get('isActive'),
            login_email=data.get('loginEmail'),
            login_password=data.get('loginPassword'),
        )
        return Response(EnvironmentSerializer(obj).data)

    def delete(self, request, pk=None):
        if not EnvironmentService.soft_delete(pk):
            return Response({'error': 'Environment not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'id': pk})


class EnvironmentPublisherView(APIView):
    """/environments/active-publisher"""

    def get(self, request):
        base_url = (request.query_params.get('baseUrl') or os.environ.get('DASHBOARD_URL') or '').strip()
        environment_id = request.query_params.get('environmentId')
        if not base_url:
            return Response({'error': 'baseUrl is required'}, status=status.HTTP_400_BAD_REQUEST)
        pub = EnvironmentService.detect_publisher(base_url, environment_id)
        if not pub:
            return Response({
                'publisher': None,
                'detail': 'No valid stored session, or the publisher could not be detected. '
                          'Log in to the dashboard for the publisher you want to test.',
            })
        return Response({'publisher': pub})

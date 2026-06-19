import uuid
from datetime import datetime, timezone

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

from core.models import Environment


def _serialize_env(env):
    return {
        'id': env.id,
        'name': env.name,
        'baseUrl': env.base_url,
        'description': env.description,
        'isActive': env.is_active,
        'createdAt': env.created_at,
        'loginEmail': env.login_email,
        'hasPassword': bool(env.login_password),
    }


class EnvironmentListCreate(APIView):
    def get(self, request):
        envs = Environment.objects.all().order_by('-created_at')
        data = [_serialize_env(e) for e in envs]
        return Response(data)

    def post(self, request):
        body = request.data
        name = (body.get('name') or '').strip()
        base_url = (body.get('baseUrl') or '').strip()
        login_email = (body.get('loginEmail') or '').strip()
        login_password = (body.get('loginPassword') or '').strip()

        if not name:
            return Response({'error': 'name is required'}, status=status.HTTP_400_BAD_REQUEST)
        if not base_url:
            return Response({'error': 'baseUrl is required'}, status=status.HTTP_400_BAD_REQUEST)
        if not login_email:
            return Response({'error': 'loginEmail is required'}, status=status.HTTP_400_BAD_REQUEST)
        if not login_password:
            return Response({'error': 'loginPassword is required'}, status=status.HTTP_400_BAD_REQUEST)

        now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        env = Environment.objects.create(
            id=str(uuid.uuid4()),
            name=name,
            base_url=base_url,
            description=(body.get('description') or '').strip(),
            is_active=body.get('isActive', True),
            created_at=now,
            login_email=login_email,
            login_password=login_password,
        )
        return Response(_serialize_env(env), status=status.HTTP_201_CREATED)


class EnvironmentUpdateDelete(APIView):
    def put(self, request, id):
        try:
            env = Environment.objects.get(id=id)
        except Environment.DoesNotExist:
            return Response({'error': 'Environment not found'}, status=status.HTTP_404_NOT_FOUND)

        body = request.data
        env.name = (body.get('name') or '').strip() or env.name
        env.base_url = (body.get('baseUrl') or '').strip() or env.base_url
        env.description = (body.get('description') or '').strip() if 'description' in body else env.description
        if 'isActive' in body:
            env.is_active = body['isActive']
        env.login_email = (body.get('loginEmail') or '').strip() or env.login_email
        new_password = (body.get('loginPassword') or '').strip()
        if new_password:
            env.login_password = new_password
        env.save()

        return Response(_serialize_env(env))

    def delete(self, request, id):
        now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        updated = Environment.objects.filter(id=id).update(deleted_at=now)
        if updated == 0:
            return Response({'error': 'Environment not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'id': id})

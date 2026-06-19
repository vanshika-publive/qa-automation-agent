import uuid
from datetime import datetime, timezone

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Count, Q

from core.models import Collection, Test


class CollectionListCreate(APIView):
    def get(self, request):
        collections = (
            Collection.objects
            .annotate(test_count=Count('tests', filter=Q(tests__deleted_at__isnull=True)))
            .order_by('-created_at')
        )
        data = [
            {
                'id': c.id,
                'name': c.name,
                'createdAt': c.created_at,
                'testCount': c.test_count,
            }
            for c in collections
        ]
        return Response(data)

    def post(self, request):
        name = (request.data.get('name') or '').strip()
        if not name:
            return Response(
                {'error': 'name is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        collection = Collection.objects.create(
            id=str(uuid.uuid4()),
            name=name,
            created_at=now,
        )
        data = {
            'id': collection.id,
            'name': collection.name,
            'createdAt': collection.created_at,
            'testCount': 0,
        }
        return Response(data, status=status.HTTP_201_CREATED)


class CollectionDelete(APIView):
    def delete(self, request, id):
        now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        updated = Collection.objects.filter(id=id).update(deleted_at=now)
        if updated == 0:
            return Response(
                {'error': 'Collection not found'},
                status=status.HTTP_404_NOT_FOUND,
            )
        Test.objects.filter(collection_id=id, deleted_at__isnull=True).update(deleted_at=now)
        return Response({'id': id})

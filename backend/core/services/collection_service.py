import uuid

from core.models import Collection, Test
from utils.datetime_utils import DateTimeUtils


class CollectionService:

    @staticmethod
    def list_all():
        return Collection.objects.with_test_count()

    @staticmethod
    def create(name: str) -> Collection:
        return Collection.objects.create(
            id=str(uuid.uuid4()),
            name=name,
            created_at=DateTimeUtils.now_iso(),
        )

    @staticmethod
    def rename(collection_id: str, name: str) -> int:
        return Collection.objects.filter(id=collection_id, deleted_at__isnull=True).update(name=name)

    @staticmethod
    def soft_delete(collection_id: str) -> int:
        now = DateTimeUtils.now_iso()
        updated = Collection.objects.filter(id=collection_id).update(deleted_at=now)
        if updated:
            Test.objects.filter(collection_id=collection_id, deleted_at__isnull=True).update(deleted_at=now)
        return updated

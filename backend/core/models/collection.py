import uuid

from django.db import models
from django.db.models import Count, Q

from core.managers import SoftDeleteManager, AllObjectsManager


class CollectionManager(SoftDeleteManager):

    def with_test_count(self):
        return self.annotate(
            test_count=Count('tests', filter=Q(tests__deleted_at__isnull=True))
        ).order_by('-created_at')


class Collection(models.Model):
    id = models.TextField(primary_key=True, default=uuid.uuid4)
    name = models.TextField()
    created_at = models.TextField()
    deleted_at = models.TextField(null=True, blank=True)

    objects = CollectionManager()
    all_objects = AllObjectsManager()

    class Meta:
        db_table = 'collections'

    def __str__(self):
        return self.name

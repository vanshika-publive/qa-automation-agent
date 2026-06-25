import uuid

from django.db import models
from django.db.models import Q

from core.managers import SoftDeleteManager, AllObjectsManager
from .collection import Collection


class Test(models.Model):
    id = models.TextField(primary_key=True, default=uuid.uuid4)
    collection = models.ForeignKey(
        Collection,
        on_delete=models.RESTRICT,
        db_column='collection_id',
        related_name='tests',
    )
    name = models.TextField()
    prompt = models.TextField(default='')
    status = models.TextField(default='active')
    environment_ids = models.TextField(default='[]')
    created_at = models.TextField()
    deleted_at = models.TextField(null=True, blank=True)

    objects = SoftDeleteManager()
    all_objects = AllObjectsManager()

    class Meta:
        db_table = 'tests'
        constraints = [
            models.CheckConstraint(
                check=Q(status__in=['active', 'deleted']),
                name='tests_status_check',
            ),
        ]

    def __str__(self):
        return self.name

    @property
    def is_active(self) -> bool:
        return self.status == 'active'

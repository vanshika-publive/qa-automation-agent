import uuid

from django.db import models

from core.managers import SoftDeleteManager, AllObjectsManager
from .test import Test


class TestPlanningMemory(models.Model):
    id = models.TextField(primary_key=True, default=uuid.uuid4)
    test = models.ForeignKey(
        Test,
        on_delete=models.RESTRICT,
        db_column='test_id',
        related_name='planning_memories',
    )
    content = models.TextField()
    created_at = models.TextField()
    updated_at = models.TextField()
    deleted_at = models.TextField(null=True, blank=True)

    objects = SoftDeleteManager()
    all_objects = AllObjectsManager()

    class Meta:
        db_table = 'test_planning_memory'

    def __str__(self):
        return f'{self.test_id}: {self.content[:40]}'

import uuid

from django.db import models

from core.managers import SoftDeleteManager, AllObjectsManager
from .test import Test


class TestPlan(models.Model):
    """The current working plan artifacts for a Test.

    Replaces the on-disk ``data/specs/<collection-slug>/<test_id>/`` files:
    ``plan.md`` (``plan_md``), ``plan-snapshots.json`` (``plan_snapshots``, JSON as
    text) and ``plan-prompt.txt`` (``plan_prompt``). One row per Test.

    Distinct from ``Test.latest_good_plan``, which keeps the last plan that PASSED;
    ``plan_md`` here is the current working plan the generator reads.
    """
    id = models.TextField(primary_key=True, default=uuid.uuid4)
    test = models.ForeignKey(
        Test,
        on_delete=models.RESTRICT,
        db_column='test_id',
        related_name='plan',
    )
    plan_md = models.TextField(default='')
    plan_snapshots = models.TextField(default='{}')
    plan_prompt = models.TextField(default='')
    created_at = models.TextField()
    updated_at = models.TextField()
    deleted_at = models.TextField(null=True, blank=True)

    objects = SoftDeleteManager()
    all_objects = AllObjectsManager()

    class Meta:
        db_table = 'test_plans'

    def __str__(self):
        return f'plan for {self.test_id}'

import uuid

from django.db import models
from django.db.models import F, Window
from django.db.models.functions import RowNumber

from core.managers import SoftDeleteManager, AllObjectsManager
from .test import Test
from .environment import Environment


class ExecutionQuerySet(models.QuerySet):

    def for_test(self, test_id: str):
        return self.filter(test_id=test_id)

    def for_collection(self, collection_id: str):
        return self.filter(test__collection_id=collection_id)

    def with_status(self, status_value: str):
        return self.filter(status=status_value)

    def search_by_name(self, q: str):
        return self.filter(test__name__icontains=q)

    def in_date_range(self, from_date: str = None, to_date: str = None):
        qs = self
        if from_date:
            qs = qs.filter(started_at__gte=f'{from_date}T00:00:00.000Z')
        if to_date:
            qs = qs.filter(started_at__lte=f'{to_date}T23:59:59.999Z')
        return qs

    def with_run_number(self):
        return self.annotate(
            run_number=Window(
                expression=RowNumber(),
                partition_by=F('test_id'),
                order_by=F('started_at').asc(),
            )
        )

    def with_related(self):
        return self.select_related('test', 'test__collection', 'environment')


class ExecutionManager(models.Manager.from_queryset(ExecutionQuerySet)):

    def get_queryset(self):
        return ExecutionQuerySet(self.model, using=self._db).filter(deleted_at__isnull=True)


class Execution(models.Model):
    id = models.TextField(primary_key=True, default=uuid.uuid4)
    test = models.ForeignKey(
        Test,
        on_delete=models.RESTRICT,
        db_column='test_id',
        related_name='executions',
    )
    environment = models.ForeignKey(
        Environment,
        on_delete=models.RESTRICT,
        db_column='environment_id',
        related_name='executions',
    )
    status = models.TextField()
    started_at = models.TextField()
    completed_at = models.TextField(null=True, blank=True)
    duration_ms = models.IntegerField(null=True, blank=True)
    pass_count = models.IntegerField(default=0)
    fail_count = models.IntegerField(default=0)
    total_count = models.IntegerField(default=0)
    report_dir = models.TextField(null=True, blank=True)
    deleted_at = models.TextField(null=True, blank=True)

    objects = ExecutionManager()
    all_objects = AllObjectsManager()

    class Meta:
        db_table = 'executions'

    def __str__(self):
        return f'{self.id} ({self.status})'

    @property
    def is_running(self) -> bool:
        return self.status == 'running'

    @property
    def duration_seconds(self):
        return self.duration_ms / 1000 if self.duration_ms is not None else None


class ExecutionStep(models.Model):
    id = models.TextField(primary_key=True, default=uuid.uuid4)
    execution = models.ForeignKey(
        Execution,
        on_delete=models.RESTRICT,
        db_column='execution_id',
        related_name='steps',
    )
    step_name = models.TextField()
    status = models.TextField()
    log = models.TextField(default='')
    started_at = models.TextField()
    completed_at = models.TextField(null=True, blank=True)
    # LLM token accounting — populated for orchestrator/planner/generator stages;
    # null for the runner (no LLM) and skipped stages (e.g. replayed plans).
    prompt_tokens = models.IntegerField(null=True, blank=True)
    cached_tokens = models.IntegerField(null=True, blank=True)
    completion_tokens = models.IntegerField(null=True, blank=True)
    cost_usd = models.FloatField(null=True, blank=True)
    deleted_at = models.TextField(null=True, blank=True)

    objects = SoftDeleteManager()
    all_objects = AllObjectsManager()

    class Meta:
        db_table = 'execution_steps'

    def __str__(self):
        return f'{self.step_name} ({self.status})'

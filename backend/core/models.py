import uuid
from django.db import models
from .managers import SoftDeleteManager, AllObjectsManager


class Environment(models.Model):
    id = models.TextField(primary_key=True, default=uuid.uuid4)
    name = models.TextField(null=True, blank=True)
    base_url = models.TextField(null=True, blank=True)
    description = models.TextField(default='')
    is_active = models.BooleanField(default=True)
    created_at = models.TextField()
    login_email = models.TextField(default='')
    login_password = models.TextField(default='')
    # The dashboard is multi-publisher; this names the org the tests should run against
    # (e.g. "OdishaTv - Khabar"). Blank = use whatever publisher the stored session is on.
    publisher = models.TextField(default='', null=True, blank=True)
    deleted_at = models.TextField(null=True, blank=True)

    objects = SoftDeleteManager()
    all_objects = AllObjectsManager()

    class Meta:
        db_table = 'environments'

    def __str__(self):
        return self.name or self.id


class Collection(models.Model):
    id = models.TextField(primary_key=True, default=uuid.uuid4)
    name = models.TextField()
    created_at = models.TextField()
    deleted_at = models.TextField(null=True, blank=True)

    objects = SoftDeleteManager()
    all_objects = AllObjectsManager()

    class Meta:
        db_table = 'collections'

    def __str__(self):
        return self.name


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
                check=models.Q(status__in=['active', 'deleted']),
                name='tests_status_check',
            ),
        ]

    def __str__(self):
        return self.name


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

    objects = SoftDeleteManager()
    all_objects = AllObjectsManager()

    class Meta:
        db_table = 'executions'

    def __str__(self):
        return f'{self.id} ({self.status})'


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
    deleted_at = models.TextField(null=True, blank=True)

    objects = SoftDeleteManager()
    all_objects = AllObjectsManager()

    class Meta:
        db_table = 'execution_steps'

    def __str__(self):
        return f'{self.step_name} ({self.status})'

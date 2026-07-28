import uuid

from django.db import models

from core.managers import SoftDeleteManager, AllObjectsManager
from .environment import Environment


class AuthSession(models.Model):
    """Stored MFA browser session (Playwright storage_state).

    Replaces ``data/.auth/session.json``. ``storage_state`` is the full storage
    state JSON as text. Historically a single file was shared by every pipeline
    run; readers therefore use the most-recent non-deleted row. ``environment`` is
    nullable to allow future per-environment sessions without changing semantics.
    """
    id = models.TextField(primary_key=True, default=uuid.uuid4)
    environment = models.ForeignKey(
        Environment,
        on_delete=models.RESTRICT,
        db_column='environment_id',
        related_name='sessions',
        null=True,
        blank=True,
    )
    storage_state = models.TextField(default='')
    created_at = models.TextField()
    updated_at = models.TextField()
    deleted_at = models.TextField(null=True, blank=True)

    objects = SoftDeleteManager()
    all_objects = AllObjectsManager()

    class Meta:
        db_table = 'auth_sessions'

    def __str__(self):
        return f'session {self.id} (env={self.environment_id})'

import uuid
from django.db import models
from core.managers import SoftDeleteManager, AllObjectsManager


class Environment(models.Model):
    id = models.TextField(primary_key=True, default=uuid.uuid4)
    name = models.TextField(null=True, blank=True)
    base_url = models.TextField(null=True, blank=True)
    description = models.TextField(default='')
    is_active = models.BooleanField(default=True)
    created_at = models.TextField()
    login_email = models.TextField(default='')
    login_password = models.TextField(default='')
    # Never set by the user — detected live from the dashboard session.
    publisher = models.TextField(default='', null=True, blank=True)
    deleted_at = models.TextField(null=True, blank=True)

    objects = SoftDeleteManager()
    all_objects = AllObjectsManager()

    class Meta:
        db_table = 'environments'

    def __str__(self):
        return self.name or self.id

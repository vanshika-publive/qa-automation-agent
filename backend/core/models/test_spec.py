import uuid

from django.db import models

from core.managers import SoftDeleteManager, AllObjectsManager
from .test import Test


class TestSpec(models.Model):
    """A generated pytest spec file for a Test.

    Replaces the on-disk ``data/tests/<collection-slug>/<filename>.py`` artifact.
    One Test may own several specs (its ``generated_spec_filenames``). ``content``
    is the full spec source; ``filename`` is the basename (e.g. ``test_foo.py``).
    """
    id = models.TextField(primary_key=True, default=uuid.uuid4)
    test = models.ForeignKey(
        Test,
        on_delete=models.RESTRICT,
        db_column='test_id',
        related_name='specs',
    )
    filename = models.TextField()
    content = models.TextField(default='')
    created_at = models.TextField()
    updated_at = models.TextField()
    deleted_at = models.TextField(null=True, blank=True)

    objects = SoftDeleteManager()
    all_objects = AllObjectsManager()

    class Meta:
        db_table = 'test_specs'

    def __str__(self):
        return f'{self.test_id}: {self.filename}'

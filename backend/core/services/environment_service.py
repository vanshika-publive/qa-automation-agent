import os
import uuid

from django.conf import settings

from core.models import Environment
from utils.datetime_utils import DateTimeUtils

# The stored session lives under the runtime data dir (PLAYWRIGHT_PROJECT_ROOT), same as every
# pipeline consumer — not under backend/. Kept in one place to avoid scattered __file__ tricks.
_SESSION_PATH = os.path.join(str(settings.PLAYWRIGHT_PROJECT_ROOT), '.auth', 'session.json')


class EnvironmentService:

    @staticmethod
    def list_all():
        return Environment.objects.all().order_by('-created_at')

    @staticmethod
    def create(
        name: str,
        base_url: str,
        login_email: str,
        login_password: str,
        description: str = '',
        is_active: bool = True,
    ) -> Environment:
        return Environment.objects.create(
            id=str(uuid.uuid4()),
            name=name,
            base_url=base_url,
            description=description,
            is_active=is_active,
            created_at=DateTimeUtils.now_iso(),
            login_email=login_email,
            login_password=login_password,
        )

    @staticmethod
    def update(
        environment: Environment,
        name: str = None,
        base_url: str = None,
        description: str = None,
        is_active: bool = None,
        login_email: str = None,
        login_password: str = None,
    ) -> Environment:
        if name:
            environment.name = name
        if base_url:
            environment.base_url = base_url
        if description is not None:
            environment.description = description
        if is_active is not None:
            environment.is_active = is_active
        if login_email:
            environment.login_email = login_email
        if login_password:
            environment.login_password = login_password
        environment.save()
        return environment

    @staticmethod
    def soft_delete(environment_id: str) -> int:
        return Environment.objects.filter(id=environment_id).update(deleted_at=DateTimeUtils.now_iso())

    @staticmethod
    def detect_publisher(base_url: str, environment_id: str = None) -> dict:
        from pipeline.infrastructure.publisher import PublisherDetector
        from core.services.artifact_store import ArtifactStore
        # Publisher detection reads the session file; project it from the DB if disk is empty.
        ArtifactStore.materialize_session(str(settings.PLAYWRIGHT_PROJECT_ROOT))
        pub = PublisherDetector.detect(base_url, _SESSION_PATH)
        if pub and environment_id:
            Environment.objects.filter(id=environment_id).update(publisher=pub['name'])
        return pub

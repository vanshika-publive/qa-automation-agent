import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        try:
            from .models import Execution, Environment
            import uuid
            from utils.datetime_utils import DateTimeUtils

            Execution.all_objects.filter(status='running').update(
                status='failed',
                completed_at=DateTimeUtils.now_iso(),
            )

            if Environment.objects.count() == 0:
                now = DateTimeUtils.now_iso()
                Environment.objects.create(
                    id=str(uuid.uuid4()),
                    name='Beta',
                    base_url='https://betadashboard.thepublive.com/v2',
                    description='Beta testing environment',
                    is_active=True,
                    created_at=now,
                )
                Environment.objects.create(
                    id=str(uuid.uuid4()),
                    name='Production',
                    base_url='https://dashboard.thepublive.com/v2',
                    description='Production environment',
                    is_active=True,
                    created_at=now,
                )
        except Exception:
            logger.exception('CoreConfig.ready() startup tasks failed')

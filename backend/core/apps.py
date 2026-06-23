from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        from datetime import datetime, timezone
        try:
            from .models import Execution, Environment
            import uuid

            Execution.all_objects.filter(status='running').update(
                status='failed',
                completed_at=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            )

            if Environment.objects.count() == 0:
                now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
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
            pass

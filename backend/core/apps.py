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

            # A server restart/crash mid-run orphans the run's pytest child (reparented to init,
            # PPID=1). The RunnerService 4-minute SIGKILL lives in the now-dead server process, so
            # nothing reaps it and it can spin a CPU core for hours, starving later runs. Marking the
            # DB row 'failed' below does NOT touch the leaked OS process, so kill it here first.
            self._reap_orphaned_pytest()

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

    @staticmethod
    def _reap_orphaned_pytest():
        """Kill pytest processes leaked by a prior server instance.

        The pipeline runs pytest via RunnerService with a distinctive signature
        (`-m pytest --json-report ... <PLAYWRIGHT_PROJECT_ROOT>/...`). A freshly started server has
        not spawned any of its own yet, so any live process matching that signature is an orphan from
        a previous run and is safe to kill. We kill the whole process group (RunnerService uses
        start_new_session=True, so pgid == pid) to also reap the leaked Playwright driver/chromium
        children. Best-effort and POSIX-only; never allowed to break startup.
        """
        import os
        import signal
        import subprocess

        if os.name != 'posix':
            return
        try:
            from django.conf import settings
            project_root = str(settings.PLAYWRIGHT_PROJECT_ROOT)
            result = subprocess.run(
                ['ps', '-ax', '-o', 'pid=,command='],
                capture_output=True, text=True, timeout=10,
            )
        except Exception:
            logger.exception('reaper: could not list processes')
            return

        self_pid = os.getpid()
        reaped = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            pid_str, _, cmd = line.partition(' ')
            if not pid_str.isdigit():
                continue
            pid = int(pid_str)
            if pid == self_pid:
                continue
            # Match ONLY our pipeline's pytest invocation -- never an unrelated user pytest.
            if '-m pytest' not in cmd or '--json-report' not in cmd or project_root not in cmd:
                continue
            try:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError, OSError):
                try:
                    os.kill(pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError, OSError):
                    continue
            reaped.append(pid)

        if reaped:
            logger.warning(
                'Reaped %d orphaned pipeline pytest process(es) from a prior server run: %s',
                len(reaped), reaped,
            )

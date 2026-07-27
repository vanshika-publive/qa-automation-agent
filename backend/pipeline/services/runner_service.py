import json
import os
import signal
import subprocess
import sys
import threading
from pathlib import Path

from django.conf import settings

from pipeline.constants import PIPELINE_KILL_TIMEOUT_MS

PROJECT_ROOT = settings.PLAYWRIGHT_PROJECT_ROOT


class RunnerService:

    @staticmethod
    def run(reports_dir: str, test_target=None, credentials: dict = None, execution_id: str = None) -> dict:
        os.makedirs(reports_dir, exist_ok=True)
        results_file = os.path.join(reports_dir, 'results.json')
        html_dir = os.path.join(reports_dir, 'html')
        os.makedirs(html_dir, exist_ok=True)
        html_report = os.path.join(html_dir, 'index.html')

        args = [
            sys.executable, '-m', 'pytest',
            '--json-report',
            f'--json-report-file={results_file}',
            f'--html={html_report}',
            '--self-contained-html',
            '-v',
        ]

        if test_target:
            if isinstance(test_target, list):
                args += test_target
            else:
                args.append(test_target)

        env = dict(os.environ)
        env['PLAYWRIGHT_PROJECT_ROOT'] = PROJECT_ROOT
        env['BACKEND_ROOT'] = settings.BACKEND_ROOT

        # Re-read HEADED directly from .env so it takes effect without a server restart.
        _env_file = Path(settings.BASE_DIR) / '.env'
        if _env_file.exists():
            for _line in _env_file.read_text().splitlines():
                _line = _line.strip()
                if _line.startswith('HEADED=') and not _line.startswith('#'):
                    env['HEADED'] = _line.split('=', 1)[1].strip()
                    break
        if credentials:
            env['DASHBOARD_URL'] = credentials.get('dashboard_url', '')
            env['DASHBOARD_EMAIL'] = credentials.get('dashboard_email', '')
            env['DASHBOARD_PASSWORD'] = credentials.get('dashboard_password', '')
            env['DASHBOARD_PUBLISHER'] = credentials.get('dashboard_publisher', '') or ''

        # slow_mo: pytest-playwright's --slowmo pauses before each Playwright action so a HEADED
        # run is watchable live. Only when headed (someone's watching) — headless CI
        # stays full-speed. Tunable via the SLOW_MO_MS env/Railway var without touching code.
        # This lives here (backend/, shipped in the image) rather than in data/tests/conftest.py,
        # which sits on a Railway volume that git deploys don't update.
        # slow_mo adds up across actions, so give slowed runs a longer per-test timeout than the
        # normal 30s, otherwise pytest-timeout kills the test mid-action.
        headed = env.get('HEADED', '').strip().lower() in ('true', '1', 'yes')
        print(f"Running tests with HEADED={headed} (SLOW_MO_MS={env.get('SLOW_MO_MS', '0')})")
        slow_mo = int(env.get('SLOW_MO_MS', '1000')) if headed else 0
        args.append(f'--timeout={120 if slow_mo > 0 else 30}')
        if slow_mo > 0:
            args.append(f'--slowmo={slow_mo}')

        proc = subprocess.Popen(
            args,
            cwd=PROJECT_ROOT,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            start_new_session=True,
        )

        # Expose the pytest process group so a stop request can SIGKILL it immediately
        # rather than waiting out the kill timeout below.
        if execution_id:
            from pipeline.utils.cancellation import CancellationRegistry
            CancellationRegistry.register_process(execution_id, proc)

        output_lines = []

        def _read_stream(stream):
            for line in stream:
                line = line.rstrip()
                if line:
                    print(line)
                    output_lines.append(line)

        stdout_thread = threading.Thread(target=_read_stream, args=(proc.stdout,), daemon=True)
        stderr_thread = threading.Thread(target=_read_stream, args=(proc.stderr,), daemon=True)
        stdout_thread.start()
        stderr_thread.start()

        timeout_s = PIPELINE_KILL_TIMEOUT_MS / 1000
        timed_out = False
        try:
            proc.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            timed_out = True
        finally:
            RunnerService._terminate_process_tree(proc)
            if execution_id:
                from pipeline.utils.cancellation import CancellationRegistry
                CancellationRegistry.clear_process(execution_id)

        stdout_thread.join(timeout=5)
        stderr_thread.join(timeout=5)

        if timed_out:
            raise RuntimeError(
                f'pytest process exceeded {PIPELINE_KILL_TIMEOUT_MS / 60_000:.0f} minute timeout; '
                'the whole process tree was killed.'
            )

        summary = RunnerService._parse_results(reports_dir)

        if summary['total'] == 0:
            return_code = proc.returncode or 0
            if return_code != 0:
                summary['failed'] = 1
                summary['failures'].append({
                    'title': 'No tests found or executed',
                    'error': f'pytest exited with code {return_code}. Check that test files exist and match test_*.py naming.',
                    'file': '',
                })

        RunnerService._print_summary(summary)
        return summary

    @staticmethod
    def _parse_results(reports_dir: str) -> dict:
        results_path = os.path.join(reports_dir, 'results.json')
        if not os.path.isfile(results_path):
            return {'total': 0, 'passed': 0, 'failed': 0, 'skipped': 0, 'durationMs': 0, 'failures': []}
        try:
            report = json.loads(Path(results_path).read_text(encoding='utf-8'))
        except Exception:
            return {'total': 0, 'passed': 0, 'failed': 0, 'skipped': 0, 'durationMs': 0, 'failures': []}

        summary = report.get('summary', {})
        passed = summary.get('passed', 0)
        failed = summary.get('failed', 0) + summary.get('error', 0)
        skipped = summary.get('skipped', 0) + summary.get('deselected', 0)
        duration_ms = int(report.get('duration', 0) * 1000)
        failures = []
        RunnerService._collect_failures(report.get('tests', []), failures)
        return {
            'total': summary.get('total', passed + failed + skipped),
            'passed': passed,
            'failed': failed,
            'skipped': skipped,
            'durationMs': duration_ms,
            'failures': failures,
        }

    @staticmethod
    def _collect_failures(tests: list, failures: list) -> None:
        for test_item in tests:
            if test_item.get('outcome', '') == 'passed':
                continue
            call_info = test_item.get('call', {})
            crash = call_info.get('crash', {})
            longrepr = call_info.get('longrepr', '')
            err_msg = crash.get('message', '') or (longrepr[:300] if longrepr else 'Unknown error')
            failures.append({
                'title': test_item.get('nodeid', 'Unnamed test'),
                'error': err_msg[:300],
                'file': test_item.get('nodeid', '').split('::')[0],
            })

    @staticmethod
    def _print_summary(s: dict) -> None:
        dur = f"{s['durationMs'] / 1000:.1f}"
        width = 34
        line = '-' * width
        print(f'\n+{line}+')
        print(f"|  Test Results{' ' * (width - 14)}|")
        print(f"|  Passed:   {str(s['passed']).ljust(width - 12)}|")
        print(f"|  Failed:   {str(s['failed']).ljust(width - 12)}|")
        print(f"|  Skipped:  {str(s['skipped']).ljust(width - 12)}|")
        print(f"|  Duration: {(dur + 's').ljust(width - 12)}|")
        print(f'+{line}+')
        if s['failures']:
            print('\nFailed tests:')
            for f in s['failures']:
                print(f"  FAIL {f['title']}")
                print(f"    {f['error'].split(chr(10))[0]}")

    @staticmethod
    def _terminate_process_tree(proc) -> None:
        if proc.poll() is not None:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError, OSError):
                pass
            return
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            try:
                proc.kill()
            except ProcessLookupError:
                pass
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass

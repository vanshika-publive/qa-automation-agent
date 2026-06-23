import json
import os
import signal
import subprocess
import sys
import threading
from pathlib import Path

from django.conf import settings

from .constants import PIPELINE_KILL_TIMEOUT_MS

PROJECT_ROOT = settings.PLAYWRIGHT_PROJECT_ROOT


def _collect_failures(tests, failures):
    for test_item in tests:
        outcome = test_item.get('outcome', '')
        if outcome == 'passed':
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


def _parse_results(reports_dir):
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
    all_tests = report.get('tests', [])
    _collect_failures(all_tests, failures)

    return {
        'total': summary.get('total', passed + failed + skipped),
        'passed': passed,
        'failed': failed,
        'skipped': skipped,
        'durationMs': duration_ms,
        'failures': failures,
    }


def _print_summary(s):
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


def _terminate_process_tree(proc):
    """SIGKILL the entire pytest process group so no chromium/ffmpeg/driver children are
    left orphaned (a plain proc.kill() only kills pytest itself). Safe to call repeatedly."""
    if proc.poll() is not None:
        # pytest already exited; its children normally exit with it, but make sure.
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


def run_tests(reports_dir, test_target=None, credentials=None):
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
        '--timeout=30',
        '-v',
    ]

    if test_target:
        if isinstance(test_target, list):
            args += test_target
        else:
            args.append(test_target)

    env = dict(os.environ)
    env['HEADED'] = 'true'
    env['PLAYWRIGHT_PROJECT_ROOT'] = PROJECT_ROOT
    env['BACKEND_ROOT'] = settings.BACKEND_ROOT
    if credentials:
        env['DASHBOARD_URL'] = credentials.get('dashboard_url', '')
        env['DASHBOARD_EMAIL'] = credentials.get('dashboard_email', '')
        env['DASHBOARD_PASSWORD'] = credentials.get('dashboard_password', '')
        env['DASHBOARD_PUBLISHER'] = credentials.get('dashboard_publisher', '') or ''

    proc = subprocess.Popen(
        args,
        cwd=PROJECT_ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        start_new_session=True,  # own process group, so we can kill the whole tree on timeout
    )

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
        return_code = proc.wait(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        timed_out = True
        return_code = -1
    finally:
        # Always reap the whole process tree — on timeout, on normal exit, and on any
        # exception above. This is what prevents orphaned pytest/chromium/ffmpeg processes.
        _terminate_process_tree(proc)

    stdout_thread.join(timeout=5)
    stderr_thread.join(timeout=5)

    if timed_out:
        raise RuntimeError(
            f'pytest process exceeded {PIPELINE_KILL_TIMEOUT_MS / 60_000:.0f} minute timeout; '
            'the whole process tree was killed.'
        )

    summary = _parse_results(reports_dir)

    if summary['total'] == 0 and return_code != 0:
        summary['failed'] = 1
        summary['failures'].append({
            'title': 'No tests found or executed',
            'error': f'pytest exited with code {return_code}. Check that test files exist and match test_*.py naming.',
            'file': '',
        })

    _print_summary(summary)
    return summary

import io
import os
import subprocess
import sys
import time
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings

from core.models import Test, Collection, Environment, Execution, ExecutionStep
from utils.slug import to_collection_slug
from .credential_manager import set_runtime_credentials, clear_runtime_credentials
from .login_helper import refresh_session

PROJECT_ROOT = settings.PLAYWRIGHT_PROJECT_ROOT


def _now_iso():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


class LogCapture:
    def __init__(self):
        self._lines = []
        self._orig_stdout = None
        self._orig_stderr = None

    def start(self):
        self._orig_stdout = sys.stdout
        self._orig_stderr = sys.stderr
        sys.stdout = _TeeWriter(self._orig_stdout, self._lines)
        sys.stderr = _TeeWriter(self._orig_stderr, self._lines, prefix='WARN: ')

    def flush(self):
        result = '\n'.join(self._lines)
        self._lines.clear()
        return result

    def stop(self):
        if self._orig_stdout:
            sys.stdout = self._orig_stdout
        if self._orig_stderr:
            sys.stderr = self._orig_stderr


class _TeeWriter:
    def __init__(self, orig, lines, prefix=''):
        self._orig = orig
        self._lines = lines
        self._prefix = prefix

    def write(self, text):
        if self._orig:
            self._orig.write(text)
        stripped = text.rstrip('\n')
        if stripped:
            self._lines.append(f'{self._prefix}{stripped}')

    def flush(self):
        if self._orig:
            self._orig.flush()


def _insert_step(execution_id, step_name, step_id, started_at):
    ExecutionStep.all_objects.create(
        id=step_id,
        execution_id=execution_id,
        step_name=step_name,
        status='running',
        log='',
        started_at=started_at,
    )


def _update_step(step_id, status, log, completed_at):
    ExecutionStep.all_objects.filter(id=step_id).update(
        status=status,
        log=log,
        completed_at=completed_at,
    )


def _finalize_execution(execution_id, status, start_ms, summary):
    now = _now_iso()
    duration = int(time.time() * 1000) - start_ms
    Execution.all_objects.filter(id=execution_id).update(
        status=status,
        completed_at=now,
        duration_ms=duration,
        pass_count=summary.get('passed', 0) if summary else 0,
        fail_count=summary.get('failed', 0) if summary else 0,
        total_count=summary.get('total', 0) if summary else 0,
    )


def _fetch_run_context(test_id, environment_id, include_prompt=True):
    test = Test.all_objects.select_related('collection').filter(id=test_id).first()
    if not test:
        raise RuntimeError(f'Test {test_id} not found')

    collection_slug = to_collection_slug(test.collection.name)

    env = Environment.all_objects.filter(id=environment_id).first()

    return {
        'collection_slug': collection_slug,
        'env_row': {
            'base_url': env.base_url,
            'login_email': env.login_email,
            'login_password': env.login_password,
            'publisher': env.publisher or '',
        } if env else None,
        'test_prompt': test.prompt if include_prompt else None,
    }


def run_pipeline(execution_id, test_id, environment_id, on_step=None):
    if on_step is None:
        on_step = lambda step: None

    ctx = _fetch_run_context(test_id, environment_id, include_prompt=True)
    collection_slug = ctx['collection_slug']
    env_row = ctx['env_row']
    test_prompt = ctx['test_prompt']

    test_plan_path = os.path.join(PROJECT_ROOT, 'specs', collection_slug, test_id, 'plan.md')
    tests_dir = os.path.join(PROJECT_ROOT, 'tests', collection_slug)
    reports_dir = os.path.join(PROJECT_ROOT, 'reports', collection_slug, execution_id)
    report_dir = f'{collection_slug}/{execution_id}'

    Execution.all_objects.filter(id=execution_id).update(report_dir=report_dir)

    start_ms = int(time.time() * 1000)
    overall_status = 'passed'
    summary = None
    capture = LogCapture()

    try:
        if not env_row:
            raise RuntimeError(f'Environment {environment_id} not found')
        if not env_row['login_email'] or not env_row['login_password']:
            raise RuntimeError(
                'Environment has no login credentials. '
                'Open Environments -> Edit and add your dashboard email and password.'
            )

        plan_already_exists = os.path.isfile(test_plan_path)

        set_runtime_credentials({
            'dashboard_url': env_row['base_url'],
            'dashboard_email': env_row['login_email'],
            'dashboard_password': env_row['login_password'],
            'dashboard_publisher': env_row.get('publisher', ''),
        })

        print('Refreshing browser session...')
        refresh_session(PROJECT_ROOT)
        print('Session refreshed')

        # Reused sessions can be on a different org — detect which publisher is actually active.
        from .publisher import detect_active_publisher
        active_pub = detect_active_publisher(
            env_row['base_url'], os.path.join(PROJECT_ROOT, '.auth', 'session.json'))
        env_row['publisher'] = (active_pub or {}).get('name') or ''
        if env_row['publisher']:
            print(f"Active publisher (from session): {env_row['publisher']}")
            Environment.all_objects.filter(id=environment_id).update(publisher=env_row['publisher'])
            set_runtime_credentials({
                'dashboard_url': env_row['base_url'],
                'dashboard_email': env_row['login_email'],
                'dashboard_password': env_row['login_password'],
                'dashboard_publisher': env_row['publisher'],
            })
        else:
            print('WARNING: could not detect the active publisher from the session — '
                  'proceeding with whatever publisher the session holds.')

        test_plan = None
        generated_specs = []

        steps = ['orchestrator', 'planner', 'generator', 'runner']

        for step_name in steps:
            step_id = str(uuid.uuid4())
            started_at = _now_iso()

            _insert_step(execution_id, step_name, step_id, started_at)
            on_step({'step_name': step_name, 'status': 'running'})

            capture.start()
            try:
                if step_name == 'orchestrator':
                    from .orchestrator import parse_user_intent
                    test_plan = parse_user_intent(test_prompt, env_row['base_url'])

                elif step_name == 'planner':
                    if plan_already_exists:
                        print(f'Reusing existing plan at {test_plan_path} — delete that file to force regeneration')
                    else:
                        from .planner_agent import run_planner_agent
                        run_planner_agent(test_plan, test_plan_path)

                elif step_name == 'generator':
                    if not os.path.isfile(test_plan_path):
                        raise RuntimeError(
                            f'Plan file not found at {test_plan_path}. '
                            'The planner may have failed to save it.\n'
                            'Check the planner step log for errors, then re-run.'
                        )
                    from .generator_agent import run_generator_agent
                    generated_specs = run_generator_agent(test_plan_path, tests_dir)

                    for spec_file in generated_specs:
                        try:
                            compile(Path(spec_file).read_text(encoding='utf-8'), spec_file, 'exec')
                        except SyntaxError as e:
                            raise RuntimeError(f'Generated spec has Python syntax error:\n{spec_file}: {e}')

                else:
                    from .runner import run_tests
                    run_target = generated_specs if generated_specs else tests_dir
                    summary = run_tests(reports_dir, run_target, {
                        'dashboard_url': env_row['base_url'],
                        'dashboard_email': env_row['login_email'],
                        'dashboard_password': env_row['login_password'],
                        'dashboard_publisher': env_row.get('publisher', ''),
                    })
                    if (summary or {}).get('failed', 0) > 0:
                        overall_status = 'failed'

                log = capture.flush()
                capture.stop()
                step_status = (
                    'failed' if step_name == 'runner' and (summary or {}).get('failed', 0) > 0
                    else 'passed'
                )
                _update_step(step_id, step_status, log, _now_iso())
                on_step({'step_name': step_name, 'status': step_status, 'log': log})

            except Exception as err:
                captured_log = capture.flush()
                capture.stop()
                err_msg = f'{err}\n{traceback.format_exc()}'
                log = '\n\n'.join(filter(None, [captured_log, err_msg]))
                _update_step(step_id, 'failed', log, _now_iso())
                on_step({'step_name': step_name, 'status': 'failed', 'log': log})
                overall_status = 'failed'
                break

    except Exception as outer_err:
        overall_status = 'failed'
        err_msg = f'{outer_err}\n{traceback.format_exc()}'
        print(f'[pipeline pre-step error] {err_msg}', file=sys.stderr)

        try:
            diag_step_id = str(uuid.uuid4())
            now = _now_iso()
            ExecutionStep.all_objects.create(
                id=diag_step_id,
                execution_id=execution_id,
                step_name='orchestrator',
                status='failed',
                log=f'Pipeline failed before tests ran:\n\n{err_msg}',
                started_at=now,
                completed_at=now,
            )
            on_step({'step_name': 'orchestrator', 'status': 'failed', 'log': err_msg})
        except Exception:
            pass

    finally:
        clear_runtime_credentials()
        _finalize_execution(execution_id, overall_status, start_ms, summary)


def run_spec_file(execution_id, test_id, spec_filename, environment_id, on_step=None):
    if on_step is None:
        on_step = lambda step: None

    ctx = _fetch_run_context(test_id, environment_id, include_prompt=False)
    collection_slug = ctx['collection_slug']
    env_row = ctx['env_row']

    spec_abs_path = os.path.join(PROJECT_ROOT, 'tests', spec_filename)
    reports_dir = os.path.join(PROJECT_ROOT, 'reports', collection_slug, execution_id)
    report_dir = f'{collection_slug}/{execution_id}'

    Execution.all_objects.filter(id=execution_id).update(report_dir=report_dir)

    start_ms = int(time.time() * 1000)
    overall_status = 'passed'
    summary = None
    capture = LogCapture()

    try:
        if not env_row:
            raise RuntimeError(f'Environment {environment_id} not found')
        if not env_row['login_email'] or not env_row['login_password']:
            raise RuntimeError(
                'Environment has no login credentials. '
                'Open Environments -> Edit and add your dashboard email and password.'
            )

        set_runtime_credentials({
            'dashboard_url': env_row['base_url'],
            'dashboard_email': env_row['login_email'],
            'dashboard_password': env_row['login_password'],
            'dashboard_publisher': env_row.get('publisher', ''),
        })

        print('Refreshing browser session...')
        refresh_session(PROJECT_ROOT)
        print('Session refreshed')

        # Reused sessions can be on a different org — detect which publisher is actually active.
        from .publisher import detect_active_publisher
        active_pub = detect_active_publisher(
            env_row['base_url'], os.path.join(PROJECT_ROOT, '.auth', 'session.json'))
        env_row['publisher'] = (active_pub or {}).get('name') or ''
        if env_row['publisher']:
            print(f"Active publisher (from session): {env_row['publisher']}")
            Environment.all_objects.filter(id=environment_id).update(publisher=env_row['publisher'])
            set_runtime_credentials({
                'dashboard_url': env_row['base_url'],
                'dashboard_email': env_row['login_email'],
                'dashboard_password': env_row['login_password'],
                'dashboard_publisher': env_row['publisher'],
            })
        else:
            print('WARNING: could not detect the active publisher from the session — '
                  'proceeding with whatever publisher the session holds.')

        step_name = 'runner'
        step_id = str(uuid.uuid4())
        started_at = _now_iso()

        _insert_step(execution_id, step_name, step_id, started_at)
        on_step({'step_name': step_name, 'status': 'running'})

        capture.start()
        try:
            from .runner import run_tests
            summary = run_tests(reports_dir, spec_abs_path, {
                'dashboard_url': env_row['base_url'],
                'dashboard_email': env_row['login_email'],
                'dashboard_password': env_row['login_password'],
                'dashboard_publisher': env_row.get('publisher', ''),
            })
            if summary.get('failed', 0) > 0:
                overall_status = 'failed'

            log = capture.flush()
            capture.stop()
            runner_status = 'failed' if summary.get('failed', 0) > 0 else 'passed'
            _update_step(step_id, runner_status, log, _now_iso())
            on_step({'step_name': step_name, 'status': runner_status, 'log': log})

        except Exception as err:
            captured_log = capture.flush()
            capture.stop()
            err_msg = f'{err}\n{traceback.format_exc()}'
            log = '\n\n'.join(filter(None, [captured_log, err_msg]))
            _update_step(step_id, 'failed', log, _now_iso())
            on_step({'step_name': step_name, 'status': 'failed', 'log': log})
            overall_status = 'failed'

    except Exception as outer_err:
        overall_status = 'failed'
        err_msg = f'{outer_err}\n{traceback.format_exc()}'
        print(f'[runSpecFile pre-step error] {err_msg}', file=sys.stderr)

        try:
            diag_step_id = str(uuid.uuid4())
            now = _now_iso()
            ExecutionStep.all_objects.create(
                id=diag_step_id,
                execution_id=execution_id,
                step_name='runner',
                status='failed',
                log=f'Run failed before tests started:\n\n{err_msg}',
                started_at=now,
                completed_at=now,
            )
            on_step({'step_name': 'runner', 'status': 'failed', 'log': err_msg})
        except Exception:
            pass

    finally:
        clear_runtime_credentials()
        _finalize_execution(execution_id, overall_status, start_ms, summary)

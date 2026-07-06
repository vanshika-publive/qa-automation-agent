import json
import os
import sys
import time
import traceback
import uuid
from pathlib import Path

from django.conf import settings

from core.models import Test, Environment, Execution, ExecutionStep
from pipeline.infrastructure.login_helper import SessionManager
from pipeline.infrastructure.publisher import PublisherDetector
from pipeline.utils.cancellation import CancellationRegistry
from pipeline.utils.credential_manager import CredentialManager
from pipeline.utils.log_capture import LogCapture
from pipeline.utils.step_manager import StepManager
from utils.datetime_utils import DateTimeUtils
from utils.slug import to_collection_slug

PROJECT_ROOT = settings.PLAYWRIGHT_PROJECT_ROOT


class PipelineCancelled(RuntimeError):
    """Raised when a run is stopped by the user mid-flight.

    Carries a `diagnosis` dict so the per-stage failure handler persists it to
    step-failure.json, letting the "Failure reason" panel show why the run ended.
    """
    def __init__(self, message: str = 'Stopped by user.'):
        super().__init__(message)
        self.diagnosis = {'category': 'Cancelled', 'summary': message, 'locator': None}


class PipelineRunner:

    @staticmethod
    def _raise_if_cancelled(execution_id: str) -> None:
        if CancellationRegistry.is_cancelled(execution_id):
            raise PipelineCancelled()

    @staticmethod
    def run(execution_id: str, test_id: str, environment_id: str, on_step=None) -> None:
        if on_step is None:
            on_step = lambda step: None

        ctx = PipelineRunner._fetch_run_context(test_id, environment_id, include_prompt=True)
        collection_slug = ctx['collection_slug']
        env_row = ctx['env_row']
        test_prompt = ctx['test_prompt']

        test_plan_path = os.path.join(PROJECT_ROOT, 'specs', collection_slug, test_id, 'plan.md')
        plan_prompt_path = os.path.join(PROJECT_ROOT, 'specs', collection_slug, test_id, 'plan-prompt.txt')
        tests_dir = os.path.join(PROJECT_ROOT, 'tests', collection_slug)
        reports_dir = os.path.join(PROJECT_ROOT, 'reports', collection_slug, execution_id)
        report_dir = f'{collection_slug}/{execution_id}'

        Execution.all_objects.filter(id=execution_id).update(report_dir=report_dir)

        # Pre-create all 4 steps as 'pending' so the SSE stream can report them
        # immediately — before _prepare_environment even starts.  The loop below
        # flips each one to 'running' when it actually begins.
        pre_step_ids: dict = {}
        for sn in ['orchestrator', 'planner', 'generator', 'runner']:
            sid = str(uuid.uuid4())
            ExecutionStep.all_objects.create(
                id=sid,
                execution_id=execution_id,
                step_name=sn,
                status='pending',
                log='',
                started_at=DateTimeUtils.now_iso(),
            )
            pre_step_ids[sn] = sid

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
            if plan_already_exists:
                try:
                    stored_prompt = Path(plan_prompt_path).read_text(encoding='utf-8').strip()
                except FileNotFoundError:
                    stored_prompt = None
                if stored_prompt != test_prompt.strip():
                    print('Test prompt has changed since the last plan was generated — invalidating plan and specs.')
                    Path(test_plan_path).unlink(missing_ok=True)
                    snapshot_path = test_plan_path.replace('plan.md', 'plan-snapshots.json')
                    Path(snapshot_path).unlink(missing_ok=True)
                    plan_already_exists = False

            PipelineRunner._prepare_environment(env_row, environment_id)

            test_plan = None
            generated_specs = []

            for step_name in ['orchestrator', 'planner', 'generator', 'runner']:
                step_id = pre_step_ids[step_name]
                started_at = DateTimeUtils.now_iso()
                ExecutionStep.all_objects.filter(id=step_id).update(
                    status='running',
                    started_at=started_at,
                )
                on_step({'step_name': step_name, 'status': 'running'})

                capture.start()
                try:
                    # A stop requested before this stage begins aborts here; a stop during
                    # the runner is caught right after its subprocess is killed (below).
                    PipelineRunner._raise_if_cancelled(execution_id)

                    if step_name == 'orchestrator':
                        from pipeline.services.orchestrator_service import OrchestratorService
                        test_plan = OrchestratorService.run(test_prompt, env_row['base_url'])

                    elif step_name == 'planner':
                        if plan_already_exists:
                            print(f'Reusing existing plan at {test_plan_path} — delete it to force regeneration')
                        else:
                            from pipeline.services.planner_service import PlannerService
                            PlannerService.run(test_plan, test_plan_path)
                            Path(plan_prompt_path).write_text(test_prompt.strip(), encoding='utf-8')

                    elif step_name == 'generator':
                        if not os.path.isfile(test_plan_path):
                            raise RuntimeError(
                                f'Plan file not found at {test_plan_path}. '
                                'The planner may have failed to save it.\n'
                                'Check the planner step log for errors, then re-run.'
                            )
                        from pipeline.services.generator_service import GeneratorService
                        generated_specs = GeneratorService.run(test_plan_path, tests_dir)

                        for spec_file in generated_specs:
                            try:
                                compile(Path(spec_file).read_text(encoding='utf-8'), spec_file, 'exec')
                            except SyntaxError as e:
                                raise RuntimeError(f'Generated spec has Python syntax error:\n{spec_file}: {e}')

                        if not generated_specs:
                            raise RuntimeError(
                                'Generator produced no spec files for the plan scenarios. '
                                'Every generator_write_test attempt was rejected by the validators — '
                                'see the rejection messages in the generator step log above. '
                                'No test was written, so the run is aborted rather than silently '
                                'falling back to the collection\'s pre-existing specs. '
                                'Fix the validator rejection (or the plan) and re-run.'
                            )
                        basenames = [os.path.basename(p) for p in generated_specs]
                        Test.all_objects.filter(id=test_id).update(
                            generated_spec_filenames=json.dumps(basenames)
                        )

                    else:
                        from pipeline.services.runner_service import RunnerService
                        if not generated_specs:
                            raise RuntimeError(
                                'No generated specs to run — the generator stage produced nothing. '
                                'Refusing to run the entire collection directory as a fallback.'
                            )
                        run_target = generated_specs
                        summary = RunnerService.run(reports_dir, run_target, {
                            'dashboard_url': env_row['base_url'],
                            'dashboard_email': env_row['login_email'],
                            'dashboard_password': env_row['login_password'],
                            'dashboard_publisher': env_row.get('publisher', ''),
                        }, execution_id=execution_id)
                        # A stop kills pytest, which makes run() return normally with
                        # whatever partial results exist — force a failure so a stopped run
                        # never reports as passed.
                        PipelineRunner._raise_if_cancelled(execution_id)
                        if (summary or {}).get('failed', 0) > 0:
                            overall_status = 'failed'

                    log = capture.flush()
                    capture.stop()
                    step_status = (
                        'failed' if step_name == 'runner' and (summary or {}).get('failed', 0) > 0
                        else 'passed'
                    )
                    StepManager.update(step_id, step_status, log, DateTimeUtils.now_iso())
                    on_step({'step_name': step_name, 'status': step_status, 'log': log})

                except Exception as err:
                    captured_log = capture.flush()
                    capture.stop()
                    err_msg = f'{err}\n{traceback.format_exc()}'
                    log = '\n\n'.join(filter(None, [captured_log, err_msg]))
                    # A stage may attach a structured diagnosis (e.g. the planner's blocked-flow
                    # report). Persist it beside results.json so failure_summary can surface it in
                    # the "Failure reason" panel — otherwise a pre-runner failure has no reason.
                    PipelineRunner._write_step_failure(reports_dir, getattr(err, 'diagnosis', None))
                    StepManager.update(step_id, 'failed', log, DateTimeUtils.now_iso())
                    on_step({'step_name': step_name, 'status': 'failed', 'log': log})
                    overall_status = 'failed'
                    break

        except Exception as outer_err:
            overall_status = 'failed'
            err_msg = f'{outer_err}\n{traceback.format_exc()}'
            print(f'[pipeline pre-step error] {err_msg}', file=sys.stderr)
            try:
                # The orchestrator step was pre-created as 'pending'; mark it failed.
                now = DateTimeUtils.now_iso()
                orch_id = pre_step_ids.get('orchestrator')
                if orch_id:
                    ExecutionStep.all_objects.filter(id=orch_id).update(
                        status='failed',
                        log=f'Pipeline failed before tests ran:\n\n{err_msg}',
                        completed_at=now,
                    )
                else:
                    diag_id = str(uuid.uuid4())
                    ExecutionStep.all_objects.create(
                        id=diag_id,
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
            CredentialManager.clear()
            CancellationRegistry.discard(execution_id)
            StepManager.finalize_execution(execution_id, overall_status, start_ms, summary)

    @staticmethod
    def run_spec(execution_id: str, test_id: str, spec_filename: str, environment_id: str, on_step=None) -> None:
        if on_step is None:
            on_step = lambda step: None

        ctx = PipelineRunner._fetch_run_context(test_id, environment_id, include_prompt=False)
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

            PipelineRunner._prepare_environment(env_row, environment_id)

            step_id = str(uuid.uuid4())
            started_at = DateTimeUtils.now_iso()
            StepManager.insert(execution_id, 'runner', step_id, started_at)
            on_step({'step_name': 'runner', 'status': 'running'})

            capture.start()
            try:
                from pipeline.services.runner_service import RunnerService
                PipelineRunner._raise_if_cancelled(execution_id)
                summary = RunnerService.run(reports_dir, spec_abs_path, {
                    'dashboard_url': env_row['base_url'],
                    'dashboard_email': env_row['login_email'],
                    'dashboard_password': env_row['login_password'],
                    'dashboard_publisher': env_row.get('publisher', ''),
                }, execution_id=execution_id)
                PipelineRunner._raise_if_cancelled(execution_id)
                if summary.get('failed', 0) > 0:
                    overall_status = 'failed'
                log = capture.flush()
                capture.stop()
                runner_status = 'failed' if summary.get('failed', 0) > 0 else 'passed'
                StepManager.update(step_id, runner_status, log, DateTimeUtils.now_iso())
                on_step({'step_name': 'runner', 'status': runner_status, 'log': log})

            except Exception as err:
                captured_log = capture.flush()
                capture.stop()
                err_msg = f'{err}\n{traceback.format_exc()}'
                log = '\n\n'.join(filter(None, [captured_log, err_msg]))
                PipelineRunner._write_step_failure(reports_dir, getattr(err, 'diagnosis', None))
                StepManager.update(step_id, 'failed', log, DateTimeUtils.now_iso())
                on_step({'step_name': 'runner', 'status': 'failed', 'log': log})
                overall_status = 'failed'

        except Exception as outer_err:
            overall_status = 'failed'
            err_msg = f'{outer_err}\n{traceback.format_exc()}'
            print(f'[runSpecFile pre-step error] {err_msg}', file=sys.stderr)
            try:
                diag_id = str(uuid.uuid4())
                now = DateTimeUtils.now_iso()
                ExecutionStep.all_objects.create(
                    id=diag_id,
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
            CredentialManager.clear()
            CancellationRegistry.discard(execution_id)
            StepManager.finalize_execution(execution_id, overall_status, start_ms, summary)

    @staticmethod
    def _write_step_failure(reports_dir: str, diagnosis) -> None:
        """Persist a stage's structured failure diagnosis to reports_dir/step-failure.json.

        No-op unless the stage attached a dict diagnosis. Best-effort: a write failure here
        must never mask the original stage error.
        """
        if not isinstance(diagnosis, dict):
            return
        try:
            os.makedirs(reports_dir, exist_ok=True)
            Path(os.path.join(reports_dir, 'step-failure.json')).write_text(
                json.dumps(diagnosis, indent=2), encoding='utf-8'
            )
        except Exception as exc:
            print(f'[pipeline] could not write step-failure.json: {exc}', file=sys.stderr)

    @staticmethod
    def _fetch_run_context(test_id: str, environment_id: str, include_prompt: bool = True) -> dict:
        test = Test.all_objects.select_related('collection').filter(id=test_id).first()
        if not test:
            raise RuntimeError(f'Test {test_id} not found')
        env = Environment.all_objects.filter(id=environment_id).first()
        return {
            'collection_slug': to_collection_slug(test.collection.name),
            'env_row': {
                'base_url': env.base_url,
                'login_email': env.login_email,
                'login_password': env.login_password,
                'publisher': env.publisher or '',
            } if env else None,
            'test_prompt': test.prompt if include_prompt else None,
        }

    @staticmethod
    def _prepare_environment(env_row: dict, environment_id: str) -> None:
        """Refresh session and detect active publisher. Mutates env_row in place."""
        CredentialManager.set({
            'dashboard_url': env_row['base_url'],
            'dashboard_email': env_row['login_email'],
            'dashboard_password': env_row['login_password'],
            'dashboard_publisher': env_row.get('publisher', ''),
        })

        print('Refreshing browser session...')
        SessionManager.refresh(PROJECT_ROOT)
        print('Session refreshed')

        active_pub = PublisherDetector.detect(
            env_row['base_url'],
            os.path.join(PROJECT_ROOT, '.auth', 'session.json'),
        )
        env_row['publisher'] = (active_pub or {}).get('name') or ''
        if env_row['publisher']:
            print(f"Active publisher (from session): {env_row['publisher']}")
            Environment.all_objects.filter(id=environment_id).update(publisher=env_row['publisher'])
            CredentialManager.set({
                'dashboard_url': env_row['base_url'],
                'dashboard_email': env_row['login_email'],
                'dashboard_password': env_row['login_password'],
                'dashboard_publisher': env_row['publisher'],
            })
        else:
            print('WARNING: could not detect the active publisher — '
                  'proceeding with whatever publisher the session holds.')

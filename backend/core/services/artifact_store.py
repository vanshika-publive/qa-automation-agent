"""DB⇄disk translation for pipeline artifacts.

The DB is the source of truth for spec/plan/result/session content; disk is an
ephemeral per-run scratch area because pytest (and the @playwright/mcp subprocess)
can only read/write real files. This module is the single place that:

- ``save_*``       — persist an artifact's content into its table (the canonical copy)
- ``materialize_*``— project a table's content back onto disk before a run needs it
- ``get_*``/``list_*`` — read canonical content for the API (no disk required)

Every writer in the pipeline mirrors to the DB via ``save_*`` right after it writes
disk, so the two stay in sync; readers prefer the DB and fall back to disk only for
rows not yet backfilled/mirrored. HTML reports are intentionally NOT handled here —
they stay on disk and are served statically at ``/reports/``.
"""
import json
import os
from pathlib import Path

from core.models import (
    Test,
    TestSpec,
    TestPlan,
    Execution,
    ExecutionResult,
    AuthSession,
)
from utils.datetime_utils import DateTimeUtils
from utils.slug import to_collection_slug


class ArtifactStore:

    # ---------------------------------------------------------------- specs

    @staticmethod
    def save_spec(test_id: str, filename: str, content: str) -> None:
        """Upsert a spec's content by (test, basename). Soft-deleted rows are revived."""
        basename = os.path.basename(filename)
        now = DateTimeUtils.now_iso()
        row = TestSpec.all_objects.filter(test_id=test_id, filename=basename).first()
        if row:
            row.content = content
            row.updated_at = now
            row.deleted_at = None
            row.save(update_fields=['content', 'updated_at', 'deleted_at'])
        else:
            TestSpec.objects.create(
                test_id=test_id,
                filename=basename,
                content=content,
                created_at=now,
                updated_at=now,
            )

    @staticmethod
    def save_specs_from_paths(test_id: str, paths: list) -> None:
        """Mirror on-disk spec files (as written by the generator) into the DB."""
        for p in paths or []:
            try:
                content = Path(p).read_text(encoding='utf-8')
            except OSError:
                continue
            ArtifactStore.save_spec(test_id, os.path.basename(p), content)

    @staticmethod
    def materialize_specs(test_id: str, dest_dir: str) -> list:
        """Write all of a test's specs from the DB onto disk under ``dest_dir``.
        Returns the list of absolute paths written."""
        specs = TestSpec.objects.filter(test_id=test_id)
        if not specs:
            return []
        os.makedirs(dest_dir, exist_ok=True)
        written = []
        for spec in specs:
            abs_path = os.path.join(dest_dir, spec.filename)
            Path(abs_path).write_text(spec.content, encoding='utf-8')
            written.append(abs_path)
        return written

    @staticmethod
    def materialize_collection_specs(collection_id: str, tests_root: str, collection_slug: str) -> list:
        """Materialize every spec of every test in a collection into ``tests_root/<slug>``."""
        dest_dir = os.path.join(tests_root, collection_slug)
        written = []
        for test in Test.all_objects.filter(collection_id=collection_id):
            written += ArtifactStore.materialize_specs(test.id, dest_dir)
        return written

    @staticmethod
    def list_specs_for_test(test_id: str) -> list:
        return list(TestSpec.objects.filter(test_id=test_id))

    @staticmethod
    def resolve_spec_for_test(test):
        """The spec row to show for a test: prefer the filename(s) persisted at
        generation time (``generated_spec_filenames`` order), else the most recent."""
        from utils.json_utils import safe_json_parse
        basenames = safe_json_parse(test.generated_spec_filenames, [])
        for basename in basenames:
            row = TestSpec.objects.filter(test_id=test.id, filename=basename).first()
            if row:
                return row
        return TestSpec.objects.filter(test_id=test.id).order_by('-updated_at').first()

    @staticmethod
    def get_spec_in_collection(collection_id: str, basename: str):
        """Find a spec row by basename within a collection (for path-addressed endpoints)."""
        return TestSpec.objects.filter(
            test__collection_id=collection_id, filename=os.path.basename(basename)
        ).order_by('-updated_at').first()

    @staticmethod
    def delete_spec_in_collection(collection_id: str, basename: str) -> int:
        return TestSpec.objects.filter(
            test__collection_id=collection_id, filename=os.path.basename(basename)
        ).update(deleted_at=DateTimeUtils.now_iso())

    # ---------------------------------------------------------------- plans

    @staticmethod
    def save_plan(test_id: str, plan_md: str = None, plan_snapshots: str = None,
                  plan_prompt: str = None) -> None:
        """Upsert the current working plan for a test. Only non-None fields are updated."""
        now = DateTimeUtils.now_iso()
        row = TestPlan.all_objects.filter(test_id=test_id).first()
        if row:
            if plan_md is not None:
                row.plan_md = plan_md
            if plan_snapshots is not None:
                row.plan_snapshots = plan_snapshots
            if plan_prompt is not None:
                row.plan_prompt = plan_prompt
            row.updated_at = now
            row.deleted_at = None
            row.save()
        else:
            TestPlan.objects.create(
                test_id=test_id,
                plan_md=plan_md or '',
                plan_snapshots=plan_snapshots if plan_snapshots is not None else '{}',
                plan_prompt=plan_prompt or '',
                created_at=now,
                updated_at=now,
            )

    @staticmethod
    def save_plan_from_disk(test_id: str, plan_path: str, plan_prompt: str = None) -> None:
        """Mirror the on-disk plan.md (+ sibling plan-snapshots.json) into the DB."""
        try:
            plan_md = Path(plan_path).read_text(encoding='utf-8')
        except OSError:
            return
        snapshot_path = os.path.join(os.path.dirname(plan_path), 'plan-snapshots.json')
        try:
            plan_snapshots = Path(snapshot_path).read_text(encoding='utf-8')
        except OSError:
            plan_snapshots = None
        ArtifactStore.save_plan(test_id, plan_md, plan_snapshots, plan_prompt)

    @staticmethod
    def materialize_plan(test_id: str, plan_path: str, include_md: bool = True) -> bool:
        """Write a test's plan artifacts from the DB onto disk next to ``plan_path``.
        ``include_md=False`` writes only snapshots + prompt (plan.md owned by caller).
        Returns True if a TestPlan row existed."""
        row = TestPlan.objects.filter(test_id=test_id).first()
        if not row:
            return False
        plan_dir = os.path.dirname(plan_path)
        os.makedirs(plan_dir, exist_ok=True)
        if include_md:
            Path(plan_path).write_text(row.plan_md, encoding='utf-8')
        Path(os.path.join(plan_dir, 'plan-snapshots.json')).write_text(
            row.plan_snapshots or '{}', encoding='utf-8'
        )
        if row.plan_prompt:
            Path(os.path.join(plan_dir, 'plan-prompt.txt')).write_text(
                row.plan_prompt, encoding='utf-8'
            )
        return True

    @staticmethod
    def get_plan_md(test_id: str):
        row = TestPlan.objects.filter(test_id=test_id).first()
        return row.plan_md if row else None

    # -------------------------------------------------------------- results

    @staticmethod
    def _execution_id_from_report_dir(report_dir: str):
        """report_dir is '<collection-slug>/<execution-id>' — the id is the last segment."""
        if not report_dir:
            return None
        return report_dir.rstrip('/').split('/')[-1]

    @staticmethod
    def save_results(execution_id: str, results_json: str) -> None:
        now = DateTimeUtils.now_iso()
        row = ExecutionResult.all_objects.filter(execution_id=execution_id).first()
        if row:
            row.results_json = results_json
            row.updated_at = now
            row.deleted_at = None
            row.save(update_fields=['results_json', 'updated_at', 'deleted_at'])
        else:
            ExecutionResult.objects.create(
                execution_id=execution_id,
                results_json=results_json,
                created_at=now,
                updated_at=now,
            )

    @staticmethod
    def save_step_failure(execution_id: str, step_failure_json: str) -> None:
        now = DateTimeUtils.now_iso()
        row = ExecutionResult.all_objects.filter(execution_id=execution_id).first()
        if row:
            row.step_failure_json = step_failure_json
            row.updated_at = now
            row.deleted_at = None
            row.save(update_fields=['step_failure_json', 'updated_at', 'deleted_at'])
        else:
            ExecutionResult.objects.create(
                execution_id=execution_id,
                step_failure_json=step_failure_json,
                created_at=now,
                updated_at=now,
            )

    @staticmethod
    def get_results_json(report_dir: str):
        execution_id = ArtifactStore._execution_id_from_report_dir(report_dir)
        if not execution_id:
            return None
        row = ExecutionResult.objects.filter(execution_id=execution_id).first()
        return row.results_json if (row and row.results_json) else None

    @staticmethod
    def get_step_failure_json(report_dir: str):
        execution_id = ArtifactStore._execution_id_from_report_dir(report_dir)
        if not execution_id:
            return None
        row = ExecutionResult.objects.filter(execution_id=execution_id).first()
        return row.step_failure_json if (row and row.step_failure_json) else None

    # -------------------------------------------------------------- session

    @staticmethod
    def save_session(storage_state: str, environment_id: str = None) -> None:
        """Store the MFA storage_state. Mirrors the historical single-file model:
        upsert the row for this environment (or the single latest row when no env)."""
        now = DateTimeUtils.now_iso()
        if environment_id:
            row = AuthSession.all_objects.filter(environment_id=environment_id).order_by('-updated_at').first()
        else:
            row = AuthSession.all_objects.all().order_by('-updated_at').first()
        if row:
            row.storage_state = storage_state
            row.updated_at = now
            row.deleted_at = None
            if environment_id:
                row.environment_id = environment_id
            row.save()
        else:
            AuthSession.objects.create(
                environment_id=environment_id,
                storage_state=storage_state,
                created_at=now,
                updated_at=now,
            )

    @staticmethod
    def save_session_from_disk(session_path: str, environment_id: str = None) -> None:
        try:
            state = Path(session_path).read_text(encoding='utf-8')
        except OSError:
            return
        ArtifactStore.save_session(state, environment_id)

    @staticmethod
    def get_session_state():
        row = AuthSession.objects.all().order_by('-updated_at').first()
        return row.storage_state if row else None

    @staticmethod
    def materialize_session(project_root: str, force: bool = False) -> bool:
        """Write the newest stored session to ``<project_root>/.auth/session.json``.
        Skips when a file already exists unless ``force`` — SessionManager owns
        freshness/validity and may have just written a newer one. Returns True if written."""
        session_path = os.path.join(project_root, '.auth', 'session.json')
        if os.path.isfile(session_path) and not force:
            return False
        state = ArtifactStore.get_session_state()
        if not state:
            return False
        os.makedirs(os.path.dirname(session_path), exist_ok=True)
        Path(session_path).write_text(state, encoding='utf-8')
        return True

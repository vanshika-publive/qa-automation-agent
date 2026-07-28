"""One-time backfill of on-disk artifacts into the new tables.

Walks the runtime data dir and copies existing content into TestSpec / TestPlan /
ExecutionResult / AuthSession so nothing on disk is lost when the DB becomes the
source of truth. Idempotent (skips rows that already exist) and safe to re-run.
HTML reports are intentionally left on disk (served statically), so they are not
backfilled here.
"""
import datetime
import json
import os
import re
import uuid

from django.conf import settings
from django.db import migrations


def _slug(name):
    return re.sub(r'[^a-z0-9]+', '-', (name or '').lower()).strip('-')


def _iso_mtime(path):
    try:
        ts = os.path.getmtime(path)
    except OSError:
        ts = None
    dt = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc) if ts else \
        datetime.datetime.now(datetime.timezone.utc)
    return dt.isoformat().replace('+00:00', 'Z')


def _read(path):
    try:
        with open(path, encoding='utf-8') as fh:
            return fh.read()
    except OSError:
        return None


def backfill(apps, schema_editor):
    root = str(settings.PLAYWRIGHT_PROJECT_ROOT)
    Collection = apps.get_model('core', 'Collection')
    Test = apps.get_model('core', 'Test')
    Execution = apps.get_model('core', 'Execution')
    TestSpec = apps.get_model('core', 'TestSpec')
    TestPlan = apps.get_model('core', 'TestPlan')
    ExecutionResult = apps.get_model('core', 'ExecutionResult')
    AuthSession = apps.get_model('core', 'AuthSession')

    specs, plans, results, sessions = 0, 0, 0, 0

    # --- specs + plans (attributed per test) ---------------------------------
    collection_slug = {c.id: _slug(c.name) for c in Collection.objects.all()}
    for test in Test.objects.all():
        slug = collection_slug.get(test.collection_id)
        if not slug:
            continue

        # Specs: use the canonical generated_spec_filenames -> file mapping.
        try:
            basenames = json.loads(test.generated_spec_filenames or '[]')
        except (ValueError, TypeError):
            basenames = []
        for basename in basenames:
            abs_path = os.path.join(root, 'tests', slug, basename)
            content = _read(abs_path)
            if content is None:
                continue
            if TestSpec.objects.filter(test_id=test.id, filename=basename).exists():
                continue
            now = _iso_mtime(abs_path)
            TestSpec.objects.create(
                id=str(uuid.uuid4()), test_id=test.id, filename=basename,
                content=content, created_at=now, updated_at=now,
            )
            specs += 1

        # Plan: data/specs/<slug>/<test_id>/{plan.md,plan-snapshots.json,plan-prompt.txt}
        plan_dir = os.path.join(root, 'specs', slug, str(test.id))
        plan_md = _read(os.path.join(plan_dir, 'plan.md'))
        if plan_md is not None and not TestPlan.objects.filter(test_id=test.id).exists():
            snapshots = _read(os.path.join(plan_dir, 'plan-snapshots.json'))
            prompt = _read(os.path.join(plan_dir, 'plan-prompt.txt'))
            now = _iso_mtime(os.path.join(plan_dir, 'plan.md'))
            TestPlan.objects.create(
                id=str(uuid.uuid4()), test_id=test.id,
                plan_md=plan_md,
                plan_snapshots=snapshots if snapshots is not None else '{}',
                plan_prompt=prompt or '',
                created_at=now, updated_at=now,
            )
            plans += 1

    # --- results (attributed per execution via report_dir) -------------------
    for ex in Execution.objects.exclude(report_dir__isnull=True).exclude(report_dir=''):
        report_path = os.path.join(root, 'reports', ex.report_dir)
        results_json = _read(os.path.join(report_path, 'results.json'))
        step_failure = _read(os.path.join(report_path, 'step-failure.json'))
        if results_json is None and step_failure is None:
            continue
        if ExecutionResult.objects.filter(execution_id=ex.id).exists():
            continue
        now = _iso_mtime(os.path.join(report_path, 'results.json'))
        ExecutionResult.objects.create(
            id=str(uuid.uuid4()), execution_id=ex.id,
            results_json=results_json or '',
            step_failure_json=step_failure,
            created_at=now, updated_at=now,
        )
        results += 1

    # --- session -------------------------------------------------------------
    session_path = os.path.join(root, '.auth', 'session.json')
    state = _read(session_path)
    if state is not None and not AuthSession.objects.exists():
        now = _iso_mtime(session_path)
        AuthSession.objects.create(
            id=str(uuid.uuid4()), environment_id=None, storage_state=state,
            created_at=now, updated_at=now,
        )
        sessions += 1

    print(f'[backfill] specs={specs} plans={plans} results={results} sessions={sessions}')


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_artifact_tables'),
    ]

    operations = [
        # Reverse is a no-op — reversing past 0003 drops the tables entirely anyway.
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]

"""Bounded disk/DB growth for pipeline run artifacts.

Two independent policies, both best-effort (a retention failure must never affect a
run's outcome) and both invoked from `pipeline/run_pipeline.py` on every run's teardown
— the same spot that already wipes MCP scratch artifacts and plan-snapshots.json:

- a per-test COUNT cap on Execution history: the oldest executions beyond the most
  recent N are purged (report_dir removed from disk; Execution + its ExecutionResult
  soft-deleted, same as the manual DELETE /executions/<id> endpoint).
- a global AGE cap on failure screenshots specifically — the heaviest and least useful
  artifact once stale. Independent of the count cap: an execution still inside the
  keep-last-N window loses its screenshot once it's old enough, but keeps its HTML
  report and results.json.
"""
import os
import shutil
import time

from core.models import Execution, ExecutionResult
from pipeline.constants import EXECUTION_RETENTION_PER_TEST, SCREENSHOT_RETENTION_DAYS
from utils.datetime_utils import DateTimeUtils


class RetentionService:

    @staticmethod
    def enforce_execution_retention(
        test_id: str, project_root: str, keep: int = EXECUTION_RETENTION_PER_TEST
    ) -> int:
        """Purge executions for `test_id` beyond the most recent `keep` (by started_at).
        Returns the number purged. Best-effort: never raises."""
        if not test_id:
            return 0
        try:
            stale = list(
                Execution.objects.filter(test_id=test_id).order_by('-started_at')[keep:]
            )
        except Exception as err:
            print(f'[retention] could not list stale executions for test {test_id}: {err}')
            return 0
        removed = 0
        for execution in stale:
            try:
                RetentionService._purge_execution(execution, project_root)
                removed += 1
            except Exception as err:
                print(f'[retention] could not purge execution {execution.id}: {err}')
        return removed

    @staticmethod
    def _purge_execution(execution, project_root: str) -> None:
        now = DateTimeUtils.now_iso()
        if execution.report_dir:
            report_path = os.path.join(project_root, 'reports', execution.report_dir)
            shutil.rmtree(report_path, ignore_errors=True)
        ExecutionResult.all_objects.filter(execution_id=execution.id).update(deleted_at=now)
        execution.deleted_at = now
        execution.save(update_fields=['deleted_at'])

    @staticmethod
    def prune_old_screenshots(
        project_root: str, max_age_days: int = SCREENSHOT_RETENTION_DAYS
    ) -> int:
        """Delete failure-screenshot PNGs older than `max_age_days` from anywhere under
        reports/**/test-results/. Leaves the HTML report + results.json (and the execution
        itself) intact — only the screenshot is pruned. Returns the number removed."""
        reports_root = os.path.join(project_root, 'reports')
        if not os.path.isdir(reports_root):
            return 0
        cutoff = time.time() - max_age_days * 86400
        removed = 0
        for root, _dirs, files in os.walk(reports_root):
            if 'test-results' not in root.split(os.sep):
                continue
            for fname in files:
                if not fname.lower().endswith('.png'):
                    continue
                abs_path = os.path.join(root, fname)
                try:
                    if os.path.getmtime(abs_path) < cutoff:
                        os.remove(abs_path)
                        removed += 1
                except OSError as err:
                    print(f'[retention] could not remove screenshot {abs_path}: {err}')
        return removed

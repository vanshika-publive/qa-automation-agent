import time

from core.models import Execution, ExecutionStep
from utils.datetime_utils import DateTimeUtils


class StepManager:

    @staticmethod
    def insert(execution_id: str, step_name: str, step_id: str, started_at: str) -> None:
        ExecutionStep.all_objects.create(
            id=step_id,
            execution_id=execution_id,
            step_name=step_name,
            status='running',
            log='',
            started_at=started_at,
        )

    @staticmethod
    def update(step_id: str, step_status: str, log: str, completed_at: str) -> None:
        ExecutionStep.all_objects.filter(id=step_id).update(
            status=step_status,
            log=log,
            completed_at=completed_at,
        )

    @staticmethod
    def finalize_execution(execution_id: str, exec_status: str, start_ms: int, summary: dict) -> None:
        duration = int(time.time() * 1000) - start_ms
        Execution.all_objects.filter(id=execution_id).update(
            status=exec_status,
            completed_at=DateTimeUtils.now_iso(),
            duration_ms=duration,
            pass_count=summary.get('passed', 0) if summary else 0,
            fail_count=summary.get('failed', 0) if summary else 0,
            total_count=summary.get('total', 0) if summary else 0,
        )

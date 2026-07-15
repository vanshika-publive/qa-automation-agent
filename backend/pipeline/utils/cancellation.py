"""Cooperative cancellation for in-flight pipeline runs.

The stop endpoint flags an execution id here; the pipeline thread checks it at each
stage boundary and aborts. Stages with a killable subprocess (the runner's pytest)
register it so a stop request can SIGKILL immediately rather than waiting for the
next boundary check.

In-memory only — server restart loses the registry, but CoreConfig.ready() marks
orphaned running executions as failed on startup so that gap is covered.
"""

import threading


class _CancellationRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cancelled: set[str] = set()
        self._procs: dict[str, object] = {}

    def request(self, execution_id: str) -> None:
        """Flag a run for cancellation and kill its live subprocess, if any."""
        with self._lock:
            self._cancelled.add(execution_id)
            proc = self._procs.get(execution_id)
        if proc is not None:
            from pipeline.services.runner_service import RunnerService
            RunnerService._terminate_process_tree(proc)

    def is_cancelled(self, execution_id: str) -> bool:
        with self._lock:
            return execution_id in self._cancelled

    def register_process(self, execution_id: str, proc: object) -> None:
        """Track the current killable subprocess for an execution."""
        with self._lock:
            self._procs[execution_id] = proc

    def clear_process(self, execution_id: str) -> None:
        with self._lock:
            self._procs.pop(execution_id, None)

    def discard(self, execution_id: str) -> None:
        """Drop all state for a run once it has finished (success or failure)."""
        with self._lock:
            self._cancelled.discard(execution_id)
            self._procs.pop(execution_id, None)


CancellationRegistry = _CancellationRegistry()

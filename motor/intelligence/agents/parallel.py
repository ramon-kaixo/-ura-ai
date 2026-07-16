"""ParallelExecutor — ejecución concurrente de AgentTask con ThreadPoolExecutor."""

from __future__ import annotations

import logging
import threading
import time
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed
from dataclasses import dataclass, field

from motor.intelligence.agents.base import Agent
from motor.intelligence.agents.message import AgentResult, AgentTask

log = logging.getLogger("ura.agent.parallel")

_SENTINEL = object()


@dataclass
class ExecutionResult:
    workflow_id: str
    total_tasks: int
    completed: int = 0
    failed: int = 0
    cancelled: int = 0
    timed_out: int = 0
    elapsed_ms: float = 0.0
    results: list[AgentResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    cancelled_by_user: bool = False

    @property
    def success(self) -> bool:
        return self.failed == 0 and self.cancelled == 0 and self.timed_out == 0


class ParallelExecutor:
    def __init__(
        self,
        find_agent_fn: Callable[[str], Agent | None] | None = None,
        max_workers: int = 4,
        global_timeout: float | None = None,
        fail_fast: bool = False,
        cancel_on_error: bool = False,
    ) -> None:
        self._find_agent = find_agent_fn
        self._max_workers = max(1, max_workers)
        self._global_timeout = global_timeout
        self._fail_fast = fail_fast
        self._cancel_on_error = cancel_on_error
        self._cancelled: set[str] = set()
        self._lock = threading.RLock()

    @property
    def max_workers(self) -> int:
        return self._max_workers

    def cancel(self, workflow_id: str) -> bool:
        with self._lock:
            if workflow_id not in self._cancelled:
                self._cancelled.add(workflow_id)
                return True
            return False

    def is_cancelled(self, workflow_id: str) -> bool:
        with self._lock:
            return workflow_id in self._cancelled

    def execute(
        self,
        tasks: list[tuple[str, AgentTask]],
        workflow_id: str | None = None,
    ) -> ExecutionResult:
        wf_id = workflow_id or uuid.uuid4().hex[:12]
        start = time.monotonic()
        result = ExecutionResult(workflow_id=wf_id, total_tasks=len(tasks))

        if not tasks:
            result.elapsed_ms = (time.monotonic() - start) * 1000
            return result

        if self.is_cancelled(wf_id):
            result.cancelled = len(tasks)
            result.cancelled_by_user = True
            result.elapsed_ms = (time.monotonic() - start) * 1000
            return result

        with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            future_map = {}
            for agent_id, task in tasks:
                if self.is_cancelled(wf_id):
                    remaining = len(tasks) - len(future_map)
                    result.cancelled += remaining
                    result.cancelled_by_user = True
                    break

                future = pool.submit(self._run_single, agent_id, task, wf_id)
                future_map[future] = (agent_id, task)

            deadline = None
            if self._global_timeout is not None:
                deadline = time.monotonic() + self._global_timeout

            try:
                for future in as_completed(future_map, timeout=self._global_timeout):
                    if self.is_cancelled(wf_id):
                        result.cancelled += 1
                        continue

                    agent_id, task = future_map[future]
                    try:
                        if deadline is not None and time.monotonic() > deadline:
                            result.timed_out += 1
                            result.errors.append(f"Task {task.id} ({agent_id}): global timeout")
                            continue

                        task_result = future.result(timeout=0)
                        result.results.append(task_result)
                        if task_result.success:
                            result.completed += 1
                        else:
                            result.failed += 1
                            result.errors.append(f"Task {task.id} ({agent_id}): {task_result.error}")

                            if self._fail_fast:
                                with self._lock:
                                    self._cancelled.add(wf_id)
                                remaining = len(tasks) - len(result.results) - result.cancelled
                                result.cancelled += remaining
                                break

                            if self._cancel_on_error:
                                with self._lock:
                                    self._cancelled.add(wf_id)

                    except Exception as exc:
                        result.timed_out += 1
                        result.errors.append(f"Task {task.id} ({agent_id}): {exc}")
            except TimeoutError:
                remaining = len(tasks) - len(result.results) - result.cancelled
                result.timed_out += remaining
                items = list(future_map.values())
                for _, remaining_task in items[len(result.results) :]:
                    result.errors.append(f"Task {remaining_task.id}: timed_out")

        result.elapsed_ms = (time.monotonic() - start) * 1000
        return result

    def _run_single(self, agent_id: str, task: AgentTask, wf_id: str) -> AgentResult:
        if self.is_cancelled(wf_id):
            return AgentResult(
                task_id=task.id,
                agent_id=agent_id,
                success=False,
                output={},
                error="cancelled",
            )
        agent = self._find_agent(agent_id) if self._find_agent else None
        if agent is None:
            return AgentResult(
                task_id=task.id,
                agent_id=agent_id,
                success=False,
                output={},
                error=f"agent_not_found:{agent_id}",
            )
        try:
            return agent.run(task)
        except Exception as exc:
            return AgentResult(
                task_id=task.id,
                agent_id=agent_id,
                success=False,
                output={},
                error=str(exc),
            )

    def close(self) -> None:
        with self._lock:
            self._cancelled.clear()

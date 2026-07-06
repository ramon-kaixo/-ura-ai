"""ExecutorAgent — ejecuta tareas usando SubprocessExecutor y pipelines."""

from __future__ import annotations

import logging
import time
import uuid

from motor.core.executor import SubprocessExecutor
from motor.intelligence.agents.base import Agent
from motor.intelligence.agents.message import AgentResult, AgentRole, AgentStatus, AgentTask

log = logging.getLogger("ura.agent.executor")


class ExecutorAgent(Agent):
    def __init__(self, agent_id: str = "") -> None:
        self.id = agent_id or uuid.uuid4().hex[:12]
        self.name = "executor"
        self.role = AgentRole.EXECUTOR
        self.capabilities = ["execute", "run", "compute"]
        self.status = AgentStatus.IDLE
        self._subprocess = SubprocessExecutor()

    def run(self, task: AgentTask) -> AgentResult:
        start = time.monotonic()
        self.status = AgentStatus.BUSY
        try:
            output = self._execute(task.objective, task.input_data)
            self.status = AgentStatus.COMPLETED
            return AgentResult(
                task_id=task.id,
                agent_id=self.id,
                success=True,
                output=output,
                duration_ms=(time.monotonic() - start) * 1000,
            )
        except Exception as exc:
            self.status = AgentStatus.ERROR
            log.warning("ExecutorAgent error: %s", exc)
            return AgentResult(
                task_id=task.id,
                agent_id=self.id,
                success=False,
                error=str(exc),
                duration_ms=(time.monotonic() - start) * 1000,
            )

    def _execute(self, objective: str, input_data: dict) -> dict:
        cmd = input_data.get("cmd", ["echo", "executed:", objective])
        result = self._subprocess.run(cmd, timeout=input_data.get("timeout", 30))
        output = {
            "objective": objective,
            "stdout": result.stdout[:500],
            "stderr": result.stderr[:500],
            "returncode": result.returncode,
        }
        if result.returncode != 0 and not input_data.get("allow_failure", False):
            raise RuntimeError(f"Command failed (exit={result.returncode}): {result.stderr[:200]}")
        return output

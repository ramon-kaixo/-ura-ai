"""ValidatorAgent — valida resultados de otros agentes."""

from __future__ import annotations

import logging
import time
import uuid

from motor.intelligence.agents.base import Agent
from motor.intelligence.agents.message import AgentResult, AgentRole, AgentStatus, AgentTask

log = logging.getLogger("ura.agent.validator")


class ValidatorAgent(Agent):
    def __init__(self, agent_id: str = "") -> None:
        self.id = agent_id or uuid.uuid4().hex[:12]
        self.name = "validator"
        self.role = AgentRole.VALIDATOR
        self.capabilities = ["validate", "check", "verify"]
        self.status = AgentStatus.IDLE

    def run(self, task: AgentTask) -> AgentResult:
        start = time.monotonic()
        self.status = AgentStatus.BUSY
        try:
            valid, issues = self._validate(task.objective, task.input_data)
            return AgentResult(
                task_id=task.id,
                agent_id=self.id,
                success=valid,
                output={"valid": valid, "issues": issues},
                duration_ms=(time.monotonic() - start) * 1000,
            )
        except Exception as exc:
            log.warning("ValidatorAgent error: %s", exc)
            return AgentResult(
                task_id=task.id,
                agent_id=self.id,
                success=False,
                error=str(exc),
                duration_ms=(time.monotonic() - start) * 1000,
            )
        finally:
            self.status = AgentStatus.IDLE

    def _validate(self, objective: str, input_data: dict) -> tuple[bool, list[str]]:
        issues: list[str] = []
        result_data = input_data.get("result", {})
        if not result_data:
            issues.append("No result data provided")
        if input_data.get("require_success", True) and not result_data.get("success", True):
            issues.append("Result indicates failure")
        if input_data.get("require_output", False) and not result_data.get("output"):
            issues.append("Result has no output")
        return len(issues) == 0, issues

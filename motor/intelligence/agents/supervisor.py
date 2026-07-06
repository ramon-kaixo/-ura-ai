"""SupervisorAgent — coordina agentes, detecta errores, decide reintentos."""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable  # noqa: TC003
from typing import Any

from motor.intelligence.agents.base import Agent
from motor.intelligence.agents.message import AgentResult, AgentRole, AgentStatus, AgentTask

log = logging.getLogger("ura.agent.supervisor")

MAX_RETRIES = 2


class SupervisorAgent(Agent):
    def __init__(self, agent_id: str = "") -> None:
        self.id = agent_id or uuid.uuid4().hex[:12]
        self.name = "supervisor"
        self.role = AgentRole.SUPERVISOR
        self.capabilities = ["coordinate", "supervise", "retry"]
        self.status = AgentStatus.IDLE
        self._agents: dict[str, Any] = {}

    def register_agent(self, agent: Any) -> None:
        self._agents[agent.id] = agent

    def run(self, task: AgentTask) -> AgentResult:
        start = time.monotonic()
        self.status = AgentStatus.BUSY
        try:
            is_cancelled = task.context.get("_cancellation_check", lambda: False)
            result = self._coordinate(task.objective, task.context, is_cancelled)
            return AgentResult(
                task_id=task.id,
                agent_id=self.id,
                success=result.get("overall_success", False),
                output=result,
                duration_ms=(time.monotonic() - start) * 1000,
            )
        except Exception as exc:
            log.warning("SupervisorAgent error: %s", exc)
            return AgentResult(
                task_id=task.id,
                agent_id=self.id,
                success=False,
                error=str(exc),
                duration_ms=(time.monotonic() - start) * 1000,
            )
        finally:
            self.status = AgentStatus.IDLE

    def _coordinate(
        self, objective: str, context: dict[str, Any],
        is_cancelled: Callable[[], bool] | None = None,
    ) -> dict[str, Any]:
        steps: list[dict[str, Any]] = []
        subtasks = context.get("subtasks", [])

        for sub in subtasks:
            if is_cancelled and is_cancelled():
                steps.append({"step": sub.get("objective", "?"), "status": "cancelled", "reason": "workflow_cancelled"})
                break

            role = sub.get("agent_role")
            agent = self._find_agent(role)
            if agent is None:
                steps.append({"step": sub.get("objective", "?"), "status": "skipped", "reason": "no_agent"})
                continue

            task = AgentTask(
                objective=sub.get("objective", objective),
                agent_role=role,
                context=context,
                input_data=sub.get("input_data", {}),
                timeout=sub.get("timeout", 30),
            )

            for attempt in range(MAX_RETRIES + 1):
                if is_cancelled and is_cancelled():
                    steps.append({"step": task.objective, "status": "cancelled",
                            "attempt": attempt + 1, "reason": "workflow_cancelled"})
                    break
                try:
                    result = agent.run(task)
                    if result.success:
                        steps.append({"step": task.objective, "status": "completed",
                            "agent": agent.id, "attempt": attempt + 1})
                        break
                    else:
                        log.warning("Attempt %d failed for %s: %s", attempt + 1, agent.name, result.error)
                        steps.append({"step": task.objective, "status": "failed", "agent": agent.id,
                            "attempt": attempt + 1, "error": result.error})
                except Exception as exc:
                    log.warning("Exception in %s attempt %d: %s", agent.name, attempt + 1, exc)
                    steps.append({"step": task.objective, "status": "error", "agent": agent.id,
                            "attempt": attempt + 1, "error": str(exc)})

        success = all(s.get("status") == "completed" for s in steps)
        return {"overall_success": success, "steps": steps, "total_steps": len(steps)}

    def _find_agent(self, role: AgentRole | None) -> Any | None:
        if role is None:
            return None
        for agent in self._agents.values():
            if agent.role == role:
                return agent
        return None

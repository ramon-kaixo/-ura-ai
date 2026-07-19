"""PlannerAgent — divide objetivos en tareas ejecutables."""

from __future__ import annotations

import time
import uuid

from motor.intelligence.agents.base import Agent
from motor.intelligence.agents.message import AgentResult, AgentRole, AgentStatus, AgentTask


class PlannerAgent(Agent):
    def __init__(self, agent_id: str = "") -> None:
        self.id = agent_id or uuid.uuid4().hex[:12]
        self.name = "planner"
        self.role = AgentRole.PLANNER
        self.capabilities = ["plan", "decompose"]
        self.status = AgentStatus.IDLE

    def run(self, task: AgentTask) -> AgentResult:
        start = time.monotonic()
        self.status = AgentStatus.BUSY
        try:
            subtasks = self._decompose(task.objective, task.context)
            return AgentResult(
                task_id=task.id,
                agent_id=self.id,
                success=True,
                output={"subtasks": subtasks, "original_objective": task.objective},
                duration_ms=(time.monotonic() - start) * 1000,
            )
        except Exception as exc:
            return AgentResult(
                task_id=task.id,
                agent_id=self.id,
                success=False,
                error=str(exc),
                duration_ms=(time.monotonic() - start) * 1000,
            )
        finally:
            self.status = AgentStatus.IDLE

    def _decompose(self, objective: str, context: dict) -> list[dict]:
        keywords = {
            "search": AgentRole.RESEARCHER,
            "find": AgentRole.RESEARCHER,
            "lookup": AgentRole.RESEARCHER,
            "execute": AgentRole.EXECUTOR,
            "run": AgentRole.EXECUTOR,
            "compute": AgentRole.EXECUTOR,
            "validate": AgentRole.VALIDATOR,
            "check": AgentRole.VALIDATOR,
            "verify": AgentRole.VALIDATOR,
        }
        obj_lower = objective.lower()
        subtasks = []

        for keyword, role in keywords.items():
            if keyword in obj_lower:
                subtasks.append(
                    {
                        "agent_role": role,
                        "objective": objective,
                        "priority": 0,
                        "timeout": 30,
                    },
                )

        if not subtasks:
            subtasks.append(
                {
                    "agent_role": AgentRole.EXECUTOR,
                    "objective": objective,
                    "priority": 0,
                    "timeout": 30,
                },
            )

        if AgentRole.RESEARCHER in [s["agent_role"] for s in subtasks]:
            subtasks.insert(
                0,
                {
                    "agent_role": AgentRole.RESEARCHER,
                    "objective": f"Gather context for: {objective}",
                    "priority": 0,
                    "timeout": 30,
                },
            )

        return subtasks

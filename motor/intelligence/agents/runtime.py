"""MultiAgentRuntime — ejecuta workflows multiagente con trazabilidad completa."""

from __future__ import annotations

import logging
import threading
import time
import uuid
from typing import Any

from motor.intelligence.agents.base import Agent  # noqa: TC001
from motor.intelligence.agents.message import AgentResult, AgentRole, AgentTask
from motor.intelligence.agents.planner import PlannerAgent
from motor.intelligence.agents.supervisor import SupervisorAgent

log = logging.getLogger("ura.agent.runtime")

_MAX_COMPLETED = 1000


class MultiAgentRuntime:
    def __init__(self, max_completed_workflows: int = _MAX_COMPLETED) -> None:
        self._agents: dict[str, Agent] = {}
        self._workflows: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()
        self._planner = PlannerAgent()
        self._supervisor = SupervisorAgent()
        self._max_completed = max_completed_workflows

    def register(self, agent: Agent) -> str:
        with self._lock:
            self._agents[agent.id] = agent
            self._supervisor.register_agent(agent)
            log.info("Agent registered: %s (%s)", agent.name, agent.id)
            return agent.id

    def unregister(self, agent_id: str) -> bool:
        with self._lock:
            return self._agents.pop(agent_id, None) is not None

    def get_agent(self, agent_id: str) -> Agent | None:
        with self._lock:
            return self._agents.get(agent_id)

    def find_by_role(self, role: AgentRole) -> list[Agent]:
        with self._lock:
            return [a for a in self._agents.values() if a.role == role]

    def find_by_capability(self, capability: str) -> list[Agent]:
        with self._lock:
            return [a for a in self._agents.values() if capability in a.capabilities]

    def _is_cancelled(self, workflow_id: str) -> bool:
        with self._lock:
            wf2 = self._workflows.get(workflow_id)
            return wf2 is not None and wf2.get("status") == "cancelled"

    def execute_workflow(
        self,
        objective: str,
        context: dict[str, Any] | None = None,
        timeout: int = 120,
    ) -> AgentResult:
        workflow_id = uuid.uuid4().hex[:12]
        context = context or {}
        start = time.monotonic()

        with self._lock:
            self._workflows[workflow_id] = {
                "objective": objective,
                "status": "running",
            }

        def _mk_check(wf):
            return lambda: self._is_cancelled(wf)

        cancel_check = _mk_check(workflow_id)

        try:
            if cancel_check():
                return self._complete(workflow_id, False, "cancelled", start)

            plan_task = AgentTask(objective=objective, agent_role=AgentRole.PLANNER, context=context, timeout=timeout)
            plan_result = self._planner.run(plan_task)

            if not plan_result.success:
                return self._complete(workflow_id, False, plan_result.error, start)

            if cancel_check():
                return self._complete(workflow_id, False, "cancelled", start)

            subtasks = plan_result.output.get("subtasks", [])
            supervisor_context = {**context, "subtasks": subtasks, "_cancellation_check": cancel_check}

            supervisor_task = AgentTask(
                objective=objective,
                agent_role=AgentRole.SUPERVISOR,
                context=supervisor_context,
                timeout=timeout,
            )
            supervisor_result = self._supervisor.run(supervisor_task)

            if cancel_check():
                return self._complete(workflow_id, False, "cancelled", start)

            return self._complete(
                workflow_id,
                supervisor_result.success,
                "",
                start,
                {"plan": plan_result.output, "supervisor": supervisor_result.output},
            )

        except Exception as exc:
            log.exception("Workflow %s failed", workflow_id)
            return self._complete(workflow_id, False, str(exc), start)

    def cancel(self, workflow_id: str | None = None) -> bool | int:
        if workflow_id is None:
            return sum(self.cancel(wid) for wid in list(self._workflows))
        with self._lock:
            wf = self._workflows.get(workflow_id)
            if wf and wf["status"] == "running":
                wf["status"] = "cancelled"
                return True
            return False

    def get_workflow(self, workflow_id: str) -> dict[str, Any] | None:
        with self._lock:
            return self._workflows.get(workflow_id)

    def list_workflows(self) -> list[dict[str, Any]]:
        with self._lock:
            return [{"id": k, **v} for k, v in self._workflows.items()]

    def agent_count(self) -> int:
        with self._lock:
            return len(self._agents)

    def _complete(self, wf_id: str, success: bool, error: str, start: float, extra: dict | None = None) -> AgentResult:
        elapsed = (time.monotonic() - start) * 1000
        with self._lock:
            if wf_id in self._workflows:
                status = "cancelled" if error == "cancelled" else ("completed" if success else "failed")
                self._workflows[wf_id]["status"] = status
            self._trim_workflows()
        output = {"workflow_id": wf_id}
        if extra:
            output.update(extra)
        return AgentResult(
            task_id=wf_id,
            agent_id="runtime",
            success=success,
            output=output,
            error=error,
            duration_ms=round(elapsed, 2),
        )

    def _trim_workflows(self) -> None:
        done_statuses = ("completed", "failed", "cancelled")
        completed = [(k, v) for k, v in self._workflows.items() if v.get("status") in done_statuses]
        if len(completed) <= self._max_completed:
            return
        completed.sort(key=lambda p: p[1].get("_completed_at", ""))
        overflow = len(completed) - self._max_completed
        for i in range(min(overflow, len(completed))):
            wf_id = completed[i][0]
            # Preserve progress on active workflows
            if self._workflows[wf_id].get("status") != "running":
                del self._workflows[wf_id]

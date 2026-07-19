"""Agent — Orquestador de ejecución.

Responsabilidad única: coordinar CapabilityGate, Planner, Scheduler,
ToolRunner y AuditLogger para ejecutar una tarea de principio a fin.

No contiene lógica de planificación, autorización, ejecución de
herramientas, gestión de memoria, acceso a conocimiento, scheduling,
auditoría ni persistencia.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from motor.agents.base import Agent as AgentABC
from motor.agents.base import CapabilityGate as CapabilityGateABC
from motor.agents.models import AgentCapability

if TYPE_CHECKING:
    from motor.agents.base import AuditLogger, Planner, Scheduler, ToolRunner
    from motor.agents.models import AgentExecution, AgentResult, AgentState, AgentTask


class AgentOrchestrator(AgentABC):
    """Orquestador de ejecución de agentes.

    Inyectar todos los componentes vía constructor.
    No importa implementaciones concretas. Solo ABCs.
    """

    def __init__(
        self,
        planner: Planner,
        scheduler: Scheduler,
        tool_runner: ToolRunner,
        gate: CapabilityGateABC,
        audit_logger: AuditLogger,
    ) -> None:
        self._planner = planner
        self._scheduler = scheduler
        self._tool_runner = tool_runner
        self._gate = gate
        self._audit_logger = audit_logger
        self._executions: dict[str, AgentExecution] = {}
        self._required_capabilities: dict[str, AgentCapability] = {
            "retrieve": AgentCapability.FACTS_READ,
            "search": AgentCapability.WEB_SEARCH,
            "fetch": AgentCapability.WEB_FETCH,
            "tool": AgentCapability.TOOLS_EXECUTE,
            "llm": AgentCapability.MEMORY_READ,
        }

    def run(self, task: AgentTask) -> AgentResult:
        """Ejecuta una tarea y retorna el resultado.

        Cada paso del plan requiere una capability específica.
        CapabilityGate verifica antes de cada operación.
        """
        from motor.agents.models import AgentExecution, AgentState, make_agent_id

        agent_id = make_agent_id(task.task_id, time.time())

        from motor.agents.models import AgentPolicy

        execution = AgentExecution(
            agent_id=agent_id,
            task=task,
            capabilities=self._gate.capabilities(),
            policy=AgentPolicy(),
            state=AgentState.CREATED,
        )

        self._executions[agent_id] = execution
        start_time = time.time()

        try:
            # 1. Verificar permiso para planificar
            self._gate.check(AgentCapability.MEMORY_READ)
            self._transition(execution, AgentState.PLANNING)
            plan = self._planner.plan(task)
            execution.plan = plan
            self._transition(execution, AgentState.READY)

            # 2. Ejecutar via Scheduler
            self._gate.check(AgentCapability.MEMORY_READ)
            self._transition(execution, AgentState.RUNNING)
            self._scheduler.submit(execution)

            # 3. Ejecutar pasos del plan via ToolRunner
            for step in plan.steps:
                if execution.cancelled:
                    return self._finalize(execution, AgentState.CANCELLED, start_time)

                if execution.cost_units >= execution.policy.max_cost_units:
                    return self._finalize(execution, AgentState.CANCELLED, start_time, error="Budget exceeded")

                # Verificar capability para esta acción
                required = self._required_capabilities.get(step.action)
                if required is not None:
                    try:
                        self._gate.check(required)
                    except PermissionError:
                        return self._finalize(
                            execution,
                            AgentState.PERMISSION_DENIED,
                            start_time,
                            error=f"Missing capability '{required.value}' for action '{step.action}'",
                        )

                self._tool_runner.run(step.action, step.params)
                execution.cost_units += 1
                if hasattr(step, "action") and step.action == "llm":
                    execution.llm_calls += 1

            return self._finalize(execution, AgentState.COMPLETED, start_time)

        except PermissionError as e:
            return self._finalize(execution, AgentState.PERMISSION_DENIED, start_time, error=str(e))
        except Exception as e:
            return self._finalize(execution, AgentState.FAILED, start_time, error=str(e))

    def cancel(self) -> None:
        for execution in self._executions.values():
            execution.cancelled = True

    # ── Internos ──────────────────────────────────────

    def _transition(self, execution: AgentExecution, target: AgentState) -> None:
        from motor.agents.state import AgentStateMachine

        sm = AgentStateMachine()
        new_state = sm.transition(execution.state, target)
        execution.state = new_state

    def _finalize(
        self,
        execution: AgentExecution,
        state: AgentState,
        start_time: float,
        error: str | None = None,
    ) -> AgentResult:
        from motor.agents.models import AgentAuditRecord, AgentResult

        duration_ms = (time.time() - start_time) * 1000

        result = AgentResult(
            agent_id=execution.agent_id,
            task_id=execution.task.task_id,
            state=state,
            steps_completed=execution.current_step,
            duration_ms=duration_ms,
            cost_units=execution.cost_units,
            error=error,
        )

        audit = AgentAuditRecord(
            agent_id=execution.agent_id,
            task_id=execution.task.task_id,
            objective=execution.task.objective,
            plan=[s.action for s in (execution.plan.steps if execution.plan else [])],
            capabilities_used=[],
            tools_used=[],
            facts_consulted=[],
            memory_consulted=[],
            llm_calls=execution.llm_calls,
            decisions=[],
            result=state.value,
            state=state.value,
            duration_ms=duration_ms,
            cost_units=execution.cost_units,
            error=error,
            timestamp=time.time(),
        )

        self._audit_logger.log(audit)
        self._executions.pop(execution.agent_id, None)
        return result

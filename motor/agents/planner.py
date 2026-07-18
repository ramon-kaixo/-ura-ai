"""Planner — generación y replanificación de planes de agente.

Responsabilidad única: producir un AgentPlan a partir de un AgentTask.
No ejecuta pasos. No gestiona el ciclo de vida del agente.
No conoce Scheduler, Agent ni ToolRunner.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from motor.agents.base import Planner as PlannerABC

if TYPE_CHECKING:
    from motor.agents.models import AgentContext, AgentPlan, AgentTask, PlanStep


class RuleBasedPlanner(PlannerABC):
    """Planner basado en reglas.

    Produce planes deterministas a partir de palabras clave en el objetivo.
    No usa LLM. No introduce no determinismo.

    Para planes basados en LLM, extender PlannerABC con una implementación
    que use motor.core.llm.generate().
    """

    def plan(self, task: AgentTask, context: AgentContext | None = None) -> AgentPlan:
        """Genera un plan determinista basado en el objetivo."""
        from motor.agents.models import AgentPlan, PlanStep, make_plan_id, make_step_id

        objective_lower = task.objective.lower()
        steps: list[PlanStep] = []
        step_index = 0

        # Palabras clave → acciones
        if "search" in objective_lower or "find" in objective_lower or "lookup" in objective_lower:
            steps.append(self._make_step(step_index, "retrieve", {"source": "memory"}))
            step_index += 1
            steps.append(self._make_step(step_index, "search", {"query": task.objective}))
            step_index += 1

        if "read" in objective_lower or "facts" in objective_lower or "knowledge" in objective_lower:
            steps.append(self._make_step(step_index, "retrieve", {"source": "facts"}))
            step_index += 1

        if "summarize" in objective_lower or "summarise" in objective_lower:
            steps.append(self._make_step(step_index, "retrieve", {"source": "memory"}))
            step_index += 1
            steps.append(self._make_step(step_index, "llm", {"action": "summarize"}))
            step_index += 1

        if "write" in objective_lower or "save" in objective_lower or "store" in objective_lower:
            steps.append(self._make_step(step_index, "retrieve", {"source": "facts"}))
            step_index += 1
            steps.append(self._make_step(step_index, "llm", {"action": "compose"}))
            step_index += 1
            steps.append(self._make_step(step_index, "tool", {"tool": "memory.write"}))
            step_index += 1

        # Siempre incluir un paso LLM para generar respuesta
        if not steps:
            steps.append(self._make_step(step_index, "retrieve", {"source": "memory"}))
            step_index += 1

        steps.append(self._make_step(step_index, "llm", {"action": "respond"}))

        plan_id = make_plan_id(task.task_id, 1)
        return AgentPlan(
            plan_id=plan_id,
            steps=tuple(steps),
            immutable=True,
        )

    def replan(
        self,
        task: AgentTask,
        current_plan: AgentPlan,
        context: AgentContext,
        failed_step: PlanStep | None = None,
    ) -> AgentPlan:
        """Genera un nuevo plan conservando pasos completados.

        Límites:
        - Máximo 2 replanificaciones (controlado por AgentExecution.plan_attempts)
        - Conserva pasos ya completados
        - Invalida pasos pendientes y los regenera
        """
        from motor.agents.models import AgentPlan, make_plan_id

        objective_lower = task.objective.lower()
        new_steps: list[PlanStep] = []
        found_failed = False

        for step in current_plan.steps:
            if step.step_id == (failed_step.step_id if failed_step else None):
                found_failed = True
                # Regenerar desde el paso fallido
                remaining = self._generate_remaining(objective_lower, step)
                new_steps.extend(remaining)
            elif not found_failed:
                new_steps.append(step)  # conservar pasos completados

        if not found_failed:
            return current_plan  # no hubo fallo, mantener plan original

        plan_id = make_plan_id(task.task_id, 2)
        return AgentPlan(
            plan_id=plan_id,
            steps=tuple(new_steps),
            immutable=True,
        )

    # ── Helpers ──────────────────────────────────────

    @staticmethod
    def _make_step(index: int, action: str, params: dict | None = None) -> PlanStep:
        from motor.agents.models import PlanStep, make_step_id
        step_id = make_step_id("plan", index)
        return PlanStep(
            step_id=step_id,
            action=action,
            params=params or {},
        )

    def _generate_remaining(self, objective: str, from_step: PlanStep) -> list[PlanStep]:
        """Genera pasos alternativos desde un punto de fallo."""
        steps: list[PlanStep] = []
        idx = 0

        if from_step.action == "search":
            # Si search falló, intentar retrieve como alternativa
            steps.append(self._make_step(idx, "retrieve", {"source": "memory", "fallback": True}))
            idx += 1
        elif from_step.action == "tool":
            # Si tool falló, intentar llm como alternativa
            steps.append(self._make_step(idx, "llm", {"action": "suggest"}))
            idx += 1
        else:
            # Fallback genérico
            steps.append(self._make_step(idx, "retrieve", {"source": "memory", "fallback": True}))
            idx += 1

        steps.append(self._make_step(idx, "llm", {"action": "respond"}))
        return steps

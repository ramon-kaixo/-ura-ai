"""Planner v3.1 — planificación multi-objetivo con dependencias.

No duplica lógica de plugin_registry.run_phase().
La envuelve para traducir objetivo → fase → tareas.
Respeta dependencias entre objetivos para ordenar la cola.
"""

from __future__ import annotations

from typing import Any

from scripts.pro.plugin_registry import run_phase
from scripts.pro.tuneladora.engine import PipelineEngine


class Planner:
    """Planificador multi-objetivo: convierte objetivos en tareas vía run_phase."""

    GOAL_PHASE_MAP = {
        "auditar": ["post"],
        "refactor": ["refactor", "post"],
        "optimizar": ["pre", "refactor", "post"],
        "documentar": ["post"],
        "test": ["pre", "post"],
    }

    def __init__(self, engine: PipelineEngine) -> None:
        self._engine = engine

    def plan_dependency_order(
        self, goals: list[dict[str, Any]], goal_manager
    ) -> list[dict[str, Any]]:
        """Ordena objetivos respetando dependencias.

        Si A depende de B, B debe ejecutarse antes que A.
        """
        ordered: list[dict[str, Any]] = []
        executed: set[str] = set()

        def _resolve(g: dict) -> None:
            if g["goal_id"] in executed:
                return
            for dep_id in g.get("dependencies", []):
                dep = goal_manager.get(dep_id)
                if dep:
                    _resolve(dep)
            if g["goal_id"] not in executed:
                ordered.append(g)
                executed.add(g["goal_id"])

        for g in sorted(goals, key=lambda x: x.get("priority_order", 99)):
            _resolve(g)
        return ordered

    def create_plan(self, goal: dict) -> dict[str, Any]:
        """Crea un plan de tareas a partir de un objetivo."""
        title = goal.get("title", "").lower()
        phases = ["pre"]
        for keyword, extra_phases in self.GOAL_PHASE_MAP.items():
            if keyword in title:
                phases.extend(extra_phases)
        phases = list(dict.fromkeys(phases))

        plan: dict[str, Any] = {
            "goal_id": goal["goal_id"],
            "phases": phases,
            "tasks": [],
            "status": "planned",
        }
        self._engine.ledger.set_plan(plan)
        self._engine.ledger.add_decision("plan_created", {"phases": phases})
        return plan

    def execute_plan(self, plan: dict, file_path: str | None = None) -> dict[str, Any]:
        """Ejecuta un plan completo. Retorna resultados por fase."""
        results: dict[str, Any] = {}
        for phase in plan.get("phases", []):
            self._engine.log.info(f"Ejecutando fase '{phase}' del plan")
            phase_result = run_phase(phase, file_path=file_path, capability="infrastructure")
            results[phase] = {
                "ok": phase_result.get("ok", 0),
                "errors": phase_result.get("errors", 0),
                "aborted_by": phase_result.get("_aborted_by"),
            }
            if phase_result.get("_aborted_by"):
                self._engine.ledger.add_decision("phase_aborted", {
                    "phase": phase, "reason": phase_result["_aborted_by"],
                })
                break
        return results

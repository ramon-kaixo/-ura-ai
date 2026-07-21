"""Planner v3.2 — planificación adaptativa multi-estrategia.

Genera múltiples estrategias para un objetivo, estima su coste,
selecciona la mejor según presupuestos y replanifica si falla.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from scripts.pro.plugin_registry import run_phase

if TYPE_CHECKING:
    from scripts.pro.tuneladora.engine import PipelineEngine

# Estrategias: diferentes combinaciones de fases para cada tipo de objetivo
STRATEGIES = {
    "auditar": [
        {"name": "rápida", "phases": ["post"], "cost_estimate": 0.3},
        {"name": "completa", "phases": ["pre", "post"], "cost_estimate": 0.5},
    ],
    "refactor": [
        {"name": "ligera", "phases": ["refactor", "post"], "cost_estimate": 0.6},
        {"name": "profunda", "phases": ["pre", "refactor", "post"], "cost_estimate": 1.0},
    ],
    "optimizar": [
        {"name": "rápida", "phases": ["refactor"], "cost_estimate": 0.4},
        {"name": "completa", "phases": ["pre", "refactor", "post"], "cost_estimate": 0.9},
    ],
    "documentar": [
        {"name": "directa", "phases": ["post"], "cost_estimate": 0.2},
    ],
    "test": [
        {"name": "mínima", "phases": ["post"], "cost_estimate": 0.3},
        {"name": "completa", "phases": ["pre", "post"], "cost_estimate": 0.5},
    ],
}

DEFAULT_STRATEGIES = [
    {"name": "mínima", "phases": ["post"], "cost_estimate": 0.3},
    {"name": "estándar", "phases": ["pre", "post"], "cost_estimate": 0.5},
    {"name": "profunda", "phases": ["pre", "refactor", "post"], "cost_estimate": 1.0},
]


class Planner:
    """Planificador adaptativo multi-estrategia."""

    def __init__(self, engine: PipelineEngine) -> None:
        self._engine = engine
        self._phase_cache: dict[str, float] = {}

    # ── Generación de estrategias ──

    def _detect_type(self, title: str) -> str:
        t = title.lower()
        for keyword in STRATEGIES:
            if keyword in t:
                return keyword
        return ""

    def generate_strategies(self, goal: dict) -> list[dict]:
        """Genera múltiples estrategias para un objetivo."""
        title = goal.get("title", "")
        goal_type = self._detect_type(title)
        candidates = STRATEGIES.get(goal_type, DEFAULT_STRATEGIES)
        budget = goal.get("budget", {})
        time_budget = budget.get("time_max_s", 3600)

        # Ajustar coste estimado según tiempos históricos de fases
        strategies = []
        for s in candidates:
            estimated_s = s["cost_estimate"] * time_budget
            strategies.append(
                {
                    "name": s["name"],
                    "phases": s["phases"],
                    "estimated_s": round(estimated_s, 0),
                    "cost": s["cost_estimate"],
                }
            )
        return strategies

    # ── Selección de estrategia ──

    def select_strategy(self, strategies: list[dict], goal: dict) -> dict:
        """Selecciona la mejor estrategia según presupuesto disponible."""
        budget = goal.get("budget", {})
        time_budget = budget.get("time_max_s", 3600)

        # Filtrar estrategias que caben en el presupuesto
        viable = [s for s in strategies if s["estimated_s"] <= time_budget * 1.2]
        if not viable:
            viable = strategies

        # Elegir la más barata que cumpla (priorizar rapidez)
        viable.sort(key=lambda s: (s["cost"], -len(s["phases"])))
        chosen = viable[0]

        self._engine.ledger.add_decision(
            "strategy_selected",
            {
                "chosen": chosen["name"],
                "phases": chosen["phases"],
                "estimated_s": chosen["estimated_s"],
                "alternatives": [s["name"] for s in strategies if s["name"] != chosen["name"]],
            },
        )
        return chosen

    # ── Creación de plan ──

    def create_plan(self, goal: dict) -> dict:
        """Crea un plan usando la mejor estrategia disponible."""
        strategies = self.generate_strategies(goal)
        chosen = self.select_strategy(strategies, goal)

        plan = {
            "goal_id": goal["goal_id"],
            "strategy": chosen["name"],
            "phases": chosen["phases"],
            "estimated_s": chosen["estimated_s"],
            "tasks": [],
            "status": "planned",
            "fallbacks": [s for s in strategies if s["name"] != chosen["name"]],
        }
        self._engine.ledger.set_plan(plan)
        self._engine.ledger.add_decision(
            "plan_created",
            {
                "strategy": chosen["name"],
                "phases": chosen["phases"],
                "estimated_s": chosen["estimated_s"],
            },
        )
        return plan

    # ── Ejecución con replanificación ──

    def execute_plan(self, plan: dict, file_path: str | None = None) -> dict:
        """Ejecuta un plan. Si una fase falla, replanifica con fallback."""
        results: dict = {}
        phases_to_run = list(plan.get("phases", []))
        fallbacks = list(plan.get("fallbacks", []))

        for phase in phases_to_run:
            self._engine.log.info(f"Ejecutando fase '{phase}' del plan ({plan['strategy']})")
            t0 = time.time()
            phase_result = run_phase(phase, file_path=file_path, capability="infrastructure")
            elapsed = round(time.time() - t0, 1)

            results[phase] = {
                "ok": phase_result.get("ok", 0),
                "errors": phase_result.get("errors", 0),
                "elapsed_s": elapsed,
                "aborted_by": phase_result.get("_aborted_by"),
            }

            if phase_result.get("_aborted_by"):
                self._engine.ledger.add_decision(
                    "phase_aborted",
                    {
                        "phase": phase,
                        "reason": phase_result["_aborted_by"],
                    },
                )

                # ── Replanificar: buscar fallback ──
                if fallbacks:
                    fb = fallbacks.pop(0)
                    self._engine.log.warning(f"Fase '{phase}' falló. Replanificando con estrategia '{fb['name']}'")
                    self._engine.ledger.add_decision(
                        "replan",
                        {
                            "from_strategy": plan["strategy"],
                            "to_strategy": fb["name"],
                            "reason": f"phase_{phase}_aborted",
                        },
                    )
                    # Ejecutar fases restantes del fallback
                    for fb_phase in fb["phases"]:
                        if fb_phase not in phases_to_run:
                            self._engine.log.info(f"  Fallback: fase '{fb_phase}'")
                            fb_result = run_phase(fb_phase, file_path=file_path, capability="infrastructure")
                            results[f"fb_{fb_phase}"] = {
                                "ok": fb_result.get("ok", 0),
                                "errors": fb_result.get("errors", 0),
                                "fallback_of": phase,
                            }
                break

        return results

    def plan_dependency_order(self, goals: list[dict], goal_manager) -> list[dict]:
        """Ordena objetivos respetando dependencias."""
        ordered: list[dict] = []
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

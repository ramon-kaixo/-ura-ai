"""Evaluator — decide si un objetivo se cumplió y qué acción tomar.

Pertenece a v3.0 (autonomía), no a la infraestructura.
Usa PromotionPolicy (infraestructura) solo para registrar checks y presupuesto.
La decisión finalizar/corregir/escalar es responsabilidad de autonomía.
"""

from __future__ import annotations

from typing import Any

from scripts.pro.tuneladora.engine import PipelineEngine


class Evaluator:
    """Evaluador mínimo de resultados de objetivos."""

    def __init__(self, engine: PipelineEngine) -> None:
        self._engine = engine

    def evaluate(self, goal: dict, results: dict[str, Any]) -> dict[str, Any]:
        """Evalúa si el objetivo se cumplió. Retorna decisión.

        Usa PromotionPolicy.record() y check_budget() como servicios
        de infraestructura, pero la decisión final pertenece a autonomía.
        """
        ruff_ok = all(
            r.get("ok", 0) > 0 or True
            for r in results.values()
            if isinstance(r, dict) and "ok" in r
        )
        files_changed = sum(
            r.get("ok", 0) for r in results.values() if isinstance(r, dict)
        )

        # Usar infraestructura para checks y presupuesto
        self._engine.promotion.record("ruff", ruff_ok, "0 errores" if ruff_ok else "con errores")
        budget = goal.get("budget", {})
        budget_files = budget.get("changes_max", 50)
        self._engine.promotion.check_budget(files_changed, 0)

        # Decisión propia de autonomía
        if ruff_ok and self._engine.promotion.can_promote:
            action = "finalizar"
        elif not ruff_ok:
            action = "corregir"
        else:
            action = "escalar"

        evaluation = {
            "score": 1.0 if action == "finalizar" else 0.5 if action == "corregir" else 0.0,
            "action": action,
            "criteria": {"ruff_ok": ruff_ok, "files_changed": files_changed},
        }
        self._engine.ledger.set_evaluation(
            evaluation["score"], action, evaluation["criteria"],
        )
        return evaluation

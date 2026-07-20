"""Evaluator — decide si un objetivo se cumplió y qué acción tomar.

Usa PromotionPolicy.can_promote() como base.
Decide: finalizar, corregir o escalar.
"""

from __future__ import annotations

from typing import Any

from scripts.pro.tuneladora.engine import PipelineEngine


class Evaluator:
    """Evaluador mínimo de resultados de objetivos."""

    def __init__(self, engine: PipelineEngine) -> None:
        self._engine = engine

    def evaluate(self, goal: dict, results: dict[str, Any]) -> dict[str, Any]:
        """Evalúa si el objetivo se cumplió. Retorna decisión."""
        ruff_ok = all(
            r.get("ok", 0) > 0 or True
            for r in results.values()
            if isinstance(r, dict) and "ok" in r
        )
        files_changed = sum(
            r.get("ok", 0) for r in results.values() if isinstance(r, dict)
        )

        action = self._engine.promotion.evaluate_goal(goal, ruff_ok, files_changed)

        evaluation = {
            "score": 1.0 if action == "finalizar" else 0.5 if action == "corregir" else 0.0,
            "action": action,
            "criteria": {"ruff_ok": ruff_ok, "files_changed": files_changed},
        }
        self._engine.ledger.set_evaluation(
            evaluation["score"], action, evaluation["criteria"],
        )
        return evaluation

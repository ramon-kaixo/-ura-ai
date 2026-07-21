"""Researcher — orquestador de investigación autónoma.

Flujo: Memoria Semántica → Hipótesis → Evidencias → Síntesis → Informe
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from scripts.pro.autonomy.memory.queries import SemanticQueries
from scripts.pro.autonomy.research.evidence import EvidenceSearcher
from scripts.pro.autonomy.research.hypothesis import HypothesisGenerator
from scripts.pro.autonomy.research.synthesis import SynthesisEngine

if TYPE_CHECKING:
    from pathlib import Path


class Researcher:
    """Investigación autónoma basada en memoria semántica."""

    def __init__(self, db_path: Path) -> None:
        self._queries = SemanticQueries(db_path)
        self._hypothesis = HypothesisGenerator(self._queries)
        self._evidence = EvidenceSearcher(self._queries)
        self._synthesis = SynthesisEngine()

    def research(self) -> dict[str, Any]:
        """Ejecuta el ciclo completo de investigación."""
        # 1. Generar hipótesis desde la memoria
        hypotheses = self._hypothesis.generate()
        conclusions = []

        # 2. Para cada hipótesis, buscar evidencias y sintetizar
        for h in hypotheses:
            evidence = self._evidence.search(h)
            conclusion = self._synthesis.synthesize(h, evidence)
            conclusions.append(conclusion)

        return {
            "total_hipotesis": len(hypotheses),
            "conclusiones": conclusions,
            "resumen": self._summary(conclusions),
        }

    def _summary(self, conclusions: list[dict]) -> dict:
        confirmadas = sum(1 for c in conclusions if c.get("veredicto") == "confirmada")
        no_concluyentes = sum(1 for c in conclusions if c.get("veredicto") == "no_concluyente")
        refutadas = sum(1 for c in conclusions if c.get("veredicto") == "refutada")
        return {
            "confirmadas": confirmadas,
            "no_concluyentes": no_concluyentes,
            "refutadas": refutadas,
        }

    def close(self) -> None:
        self._queries.close()

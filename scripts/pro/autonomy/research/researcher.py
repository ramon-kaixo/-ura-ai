"""Researcher — orquestador de investigación autónoma.

Flujo: Memoria -> Hipotesis -> Evidencias -> Sintesis -> Informe
Usa HybridMemory si esta disponible, con fallback a SemanticQueries SQLite.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from scripts.pro.autonomy.research.synthesis import SynthesisEngine

if TYPE_CHECKING:
    from pathlib import Path

    from motor.intelligence.memory.hybrid import HybridMemory


class Researcher:
    def __init__(self, db_path: Path | None = None, memory: HybridMemory | None = None) -> None:
        self._memory = memory
        self._synthesis = SynthesisEngine()
        if memory is None and db_path is not None:
            from scripts.pro.autonomy.memory.queries import SemanticQueries
            from scripts.pro.autonomy.research.evidence import EvidenceSearcher
            from scripts.pro.autonomy.research.hypothesis import HypothesisGenerator

            self._queries = SemanticQueries(db_path)
            self._hypothesis = HypothesisGenerator(self._queries)
            self._evidence = EvidenceSearcher(self._queries)
        elif memory is not None:
            self._queries = None
        else:
            msg = "Se requiere db_path o memory"
            raise ValueError(msg)

    def research(self, query: str = "", k: int = 10) -> dict[str, Any]:
        if self._memory is not None:
            return self._research_hybrid(query, k)
        hypotheses = self._hypothesis.generate()
        conclusions = []
        for h in hypotheses:
            evidence = self._evidence.search(h)
            conclusion = self._synthesis.synthesize(h, evidence)
            conclusions.append(conclusion)
        return {
            "total_hipotesis": len(hypotheses),
            "conclusiones": conclusions,
            "resumen": self._summary(conclusions),
        }

    def _research_hybrid(self, query: str, k: int) -> dict[str, Any]:
        from motor.intelligence.memory.record import MemoryType

        results = self._memory.search(query=query, k=k, memory_type=MemoryType.SEMANTIC)
        context = "\n".join(f"- {r.payload[:500]}" for r in results) if results else "Sin datos."
        synthesis = (
            f"## Investigacion: {query}\n\n"
            f"### Fuentes ({len(results)})\n{context}\n\n"
            f"### Sintesis\n"
            f"Se encontraron {len(results)} registros relevantes en la memoria."
        )
        rid = ""
        if results:
            rid = self._memory.store(
                payload=synthesis, memory_type=MemoryType.SEMANTIC,
                metadata={"type": "auto_research", "query": query},
            )
        return {"consulta": query, "fuentes": len(results), "sintesis": synthesis, "id": rid}

    def _summary(self, conclusions: list[dict]) -> dict:
        confirmadas = sum(1 for c in conclusions if c.get("veredicto") == "confirmada")
        no_concluyentes = sum(1 for c in conclusions if c.get("veredicto") == "no_concluyente")
        refutadas = sum(1 for c in conclusions if c.get("veredicto") == "refutada")
        return {"confirmadas": confirmadas, "no_concluyentes": no_concluyentes, "refutadas": refutadas}

    def close(self) -> None:
        if hasattr(self, "_queries") and self._queries is not None:
            self._queries.close()
        if getattr(self, "_memory", None) is not None:
            self._memory.close()

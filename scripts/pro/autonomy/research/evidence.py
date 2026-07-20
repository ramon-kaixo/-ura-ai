"""EvidenceSearcher — busca evidencias en la memoria semántica para contrastar hipótesis.

Para cada hipótesis, busca datos que la apoyen o la contradigan.
"""

from __future__ import annotations

from typing import Any

from scripts.pro.autonomy.memory.queries import SemanticQueries


class EvidenceSearcher:
    """Busca evidencias en la memoria semántica para una hipótesis dada."""

    def __init__(self, queries: SemanticQueries) -> None:
        self._queries = queries

    def search(self, hypothesis: dict) -> list[dict[str, Any]]:
        """Busca evidencias que apoyen o contradigan la hipótesis."""
        hid = hypothesis.get("id", "")
        evidence: list[dict[str, Any]] = []

        if hid == "H1":
            evidence = self._search_H1()
        elif hid.startswith("H3"):
            plugin = hid.replace("H3_", "")
            evidence = self._search_H3(plugin)
        elif hid == "H2":
            evidence = self._search_H2()

        return evidence

    def _search_H1(self) -> list[dict]:
        """Evidencia: comparar tiempos entre plugins."""
        slow = self._queries.slowest_plugins(limit=10)
        evidence = []
        for i, p in enumerate(slow):
            evidence.append({
                "tipo": "apoya" if i == 0 else "contexto",
                "plugin": p["plugin_name"],
                "media_s": p["avg_dur"],
                "ejecuciones": p["runs"],
                "fuente": "slowest_plugins",
            })
        return evidence

    def _search_H2(self) -> list[dict]:
        """Evidencia: tasa de promoción vs duración."""
        rate = self._queries.promotion_rate()
        return [
            {"tipo": "apoya" if rate.get("rate", 0) < 80 else "contradice",
             "total": rate.get("total", 0),
             "promocionadas": rate.get("promoted", 0),
             "tasa": rate.get("rate", 0),
             "fuente": "promotion_rate"},
        ]

    def _search_H3(self, plugin: str) -> list[dict]:
        """Evidencia: histórico de errores de un plugin."""
        stats = self._queries.plugin_stats(plugin)
        return [
            {"tipo": "apoya" if stats.get("errors", 0) > 0 else "contradice",
             "plugin": plugin,
             "ejecuciones": stats.get("runs", 0),
             "errores": stats.get("errors", 0),
             "media_s": stats.get("avg_dur", 0),
             "fuente": "plugin_stats"},
        ]

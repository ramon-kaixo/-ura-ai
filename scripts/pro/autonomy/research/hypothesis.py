"""HypothesisGenerator — genera hipótesis a partir de patrones y memoria semántica.

Una hipótesis es una afirmación comprobable del tipo:
  "El plugin X falla más cuando se ejecuta después de Y"
  "El tiempo medio de la fase post aumenta cuando hay más de N plugins"
  "Los objetivos con prioridad high tienen mayor tasa de éxito"
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.pro.autonomy.memory.queries import SemanticQueries


class HypothesisGenerator:
    """Genera hipótesis comprobables desde la memoria semántica."""

    def __init__(self, queries: SemanticQueries) -> None:
        self._queries = queries

    def generate(self) -> list[dict[str, Any]]:
        """Genera hipótesis basadas en datos reales de la memoria."""
        hypotheses: list[dict[str, Any]] = []
        stats = self._queries.total_size()
        if stats.get("execuciones", 0) < 3:
            return hypotheses

        # H1: ¿El orden de ejecución afecta al tiempo?
        slow = self._queries.slowest_plugins(limit=5)
        if len(slow) >= 2:
            first, second = slow[0], slow[1]
            hypotheses.append({
                "id": "H1",
                "title": "El orden de ejecución afecta al tiempo total",
                "claim": f"El plugin '{first['plugin_name']}' (media {first['avg_dur']}s) "
                         f"es significativamente más lento que '{second['plugin_name']}' "
                         f"(media {second['avg_dur']}s). ¿Cambiar el orden reduciría el tiempo total?",
                "evidence_count": len(slow),
                "status": "pending",
                "source": "slowest_plugins",
            })

        # H2: ¿La tasa de promoción se correlaciona con la duración?
        rate = self._queries.promotion_rate()
        if rate.get("total", 0) >= 5 and rate.get("rate", 100) < 80:
            hypotheses.append({
                "id": "H2",
                "title": "La duración de la ejecución afecta a la promoción",
                "claim": f"Solo el {rate.get('rate', 0)}% de las ejecuciones se promocionan. "
                         f"¿Las ejecuciones más largas tienen menor tasa de promoción?",
                "evidence_count": rate.get("total", 0),
                "status": "pending",
                "source": "promotion_rate",
            })

        # H3: ¿Hay plugins con tendencia de error creciente?
        for p in slow:
            if p.get("errors", 0) > 0:
                hypotheses.append({
                    "id": f"H3_{p['plugin_name']}",
                    "title": f"El plugin '{p['plugin_name']}' tiene errores recurrentes",
                    "claim": f"El plugin '{p['plugin_name']}' tiene {p['errors']} errores "
                             f"en {p['runs']} ejecuciones. ¿Es un problema de configuración o del plugin?",
                    "evidence_count": p["runs"],
                    "status": "pending",
                    "source": "plugin_errors",
                })

        return hypotheses

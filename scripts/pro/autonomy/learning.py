"""Learning Plugin — analiza el historial del ExecutionLedger.

Extrae patrones de éxito/fallo y métricas de ejecuciones anteriores.
Es el único componente 100% nuevo de v3.0.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.pro.tuneladora.engine import PipelineEngine


class LearningPlugin:
    """Aprendizaje mínimo a partir del ledger histórico."""

    def __init__(self, engine: PipelineEngine) -> None:
        self._engine = engine
        self._ledger_dir = engine.config.nervioso / "ledger"

    def analyze(self) -> dict[str, Any]:
        """Analiza el historial de ejecuciones y retorna métricas."""
        if not self._ledger_dir.exists():
            return {"error": "no ledger data", "total": 0}

        entries: list[dict[str, Any]] = []
        for f in sorted(self._ledger_dir.glob("*.json")):
            try:
                entries.append(json.loads(f.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                continue

        if not entries:
            return {"error": "empty ledger", "total": 0}

        total = len(entries)
        promoted = sum(1 for e in entries if e.get("promotion"))
        durations = [e.get("duration_ms", 0) for e in entries if e.get("duration_ms")]
        plugins_run: dict[str, list[float]] = {}
        for e in entries:
            for p, d in e.get("plugin_durations", {}).items():
                plugins_run.setdefault(p, []).append(d)

        avg_plugin_time = {
            p: round(sum(v) / len(v), 1) for p, v in plugins_run.items()
        } if plugins_run else {}

        metrics = {
            "total_ejecuciones": total,
            "tasa_promocion": round(promoted / total, 2) if total else 0,
            "duracion_media_s": round(sum(durations) / len(durations) / 1000, 1) if durations else 0,
            "plugins_ejecutados": len(plugins_run),
            "tiempo_medio_por_plugin": avg_plugin_time,
        }
        return metrics

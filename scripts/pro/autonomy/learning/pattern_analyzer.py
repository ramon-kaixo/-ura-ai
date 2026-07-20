"""PatternAnalyzer — detecta patrones repetitivos en el ExecutionLedger.

Responde:
  ¿Qué plugin falla más?
  ¿Qué fase consume más tiempo?
  ¿Qué objetivos generan más errores?
  ¿Qué herramientas producen mejores resultados?
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any


class PatternAnalyzer:
    """Analiza el historial del ExecutionLedger y detecta patrones."""

    def __init__(self, nervioso: Path) -> None:
        self._ledger_dir = nervioso / "ledger"

    def _load(self) -> list[dict[str, Any]]:
        if not self._ledger_dir.exists():
            return []
        entries = []
        for f in sorted(self._ledger_dir.glob("*.json")):
            try:
                entries.append(json.loads(f.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                continue
        return entries

    def analyze(self) -> list[dict[str, Any]]:
        """Analiza el historial completo. Retorna patrones detectados."""
        entries = self._load()
        if len(entries) < 2:
            return []

        patterns: list[dict[str, Any]] = []

        # 1. Plugin con más fallos
        plugin_errors: dict[str, int] = {}
        plugin_time: dict[str, list[float]] = {}
        for e in entries:
            for p, s in e.get("plugin_status", {}).items():
                if s != "ok":
                    plugin_errors[p] = plugin_errors.get(p, 0) + 1
            for p, d in e.get("plugin_durations", {}).items():
                plugin_time.setdefault(p, []).append(d)

        for plugin, fails in sorted(plugin_errors.items(), key=lambda x: -x[1])[:3]:
            total = sum(1 for e in entries for p in e.get("plugin_status", {}) if p == plugin)
            patterns.append({
                "pattern": f"plugin_fail_{plugin}",
                "occurrences": fails,
                "total_ejecuciones": len(entries),
                "tasa_fallo": round(fails / max(total, 1), 2) if total else 1.0,
                "severity": "high" if fails >= 3 else "medium" if fails >= 1 else "low",
                "trend": self._calc_trend(plugin, entries),
            })

        # 2. Fase más lenta
        phase_times: dict[str, list[float]] = {}
        for e in entries:
            for p, d in e.get("plugin_durations", {}).items():
                phase_times.setdefault(p, []).append(d)
        for phase, times in phase_times.items():
            if len(times) >= 2:
                avg = statistics.mean(times)
                max_t = max(times)
                if max_t > avg * 2 and max_t > 30:
                    patterns.append({
                        "pattern": f"phase_slow_{phase}",
                        "occurrences": len([t for t in times if t > avg * 2]),
                        "avg_s": round(avg, 1),
                        "max_s": round(max_t, 1),
                        "severity": "medium",
                        "trend": "stable",
                    })

        # 3. Objetivos que más fallan
        goal_results: dict[str, list[bool]] = {}
        for e in entries:
            g = e.get("goal") or {}
            title = g.get("title", "unknown") if isinstance(g, dict) else "unknown"
            success = e.get("result") in ("finalizar", "completado", "ok")
            goal_results.setdefault(title, []).append(success)

        for title, results in goal_results.items():
            if len(results) >= 2:
                fail_rate = 1 - (sum(results) / len(results))
                if fail_rate > 0.3:
                    patterns.append({
                        "pattern": f"goal_fail_{title[:30]}",
                        "occurrences": len([r for r in results if not r]),
                        "tasa_fallo": round(fail_rate, 2),
                        "severity": "medium" if fail_rate > 0.5 else "low",
                        "trend": "stable",
                    })

        return patterns

    def _calc_trend(self, plugin: str, entries: list[dict]) -> str:
        """Calcula tendencia de errores: increasing/decreasing/stable."""
        recent = [e for e in entries[-3:] if e.get("plugin_status", {}).get(plugin) != "ok"]
        older = [e for e in entries[:3] if e.get("plugin_status", {}).get(plugin) != "ok"]
        if len(recent) > len(older):
            return "increasing"
        if len(recent) < len(older):
            return "decreasing"
        return "stable"

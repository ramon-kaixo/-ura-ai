"""Learning Plugin v3.3 — aprendizaje con efecto observable.

Criterio: "La siguiente ejecución es mejor gracias a lo aprendido en la anterior."
No solo registra información: ajusta timeouts, recomienda estrategias,
detecta regresiones y sugiere mejoras accionables.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any

from scripts.pro.tuneladora.engine import PipelineEngine


class LearningPlugin:
    """Aprendizaje útil: ajusta comportamiento futuro basado en histórico."""

    def __init__(self, engine: PipelineEngine) -> None:
        self._engine = engine
        self._ledger_dir = engine.config.nervioso / "ledger"

    def _load_entries(self) -> list[dict[str, Any]]:
        if not self._ledger_dir.exists():
            return []
        entries = []
        for f in sorted(self._ledger_dir.glob("*.json")):
            try:
                entries.append(json.loads(f.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                continue
        return entries

    # ── 1. Ajuste de timeouts por plugin ──

    def recommended_timeouts(self) -> dict[str, int]:
        """Recomienda timeouts basados en duración histórica (media + 2σ).

        La siguiente ejecución usará estos timeouts en lugar de los fijos.
        """
        entries = self._load_entries()
        plugin_times: dict[str, list[float]] = {}
        for e in entries:
            for p, d in e.get("plugin_durations", {}).items():
                plugin_times.setdefault(p, []).append(d)

        recommendations = {}
        for plugin, times in plugin_times.items():
            if len(times) >= 2:
                avg = statistics.mean(times)
                stdev = statistics.stdev(times) if len(times) > 1 else avg * 0.5
                recommended = int(avg + 2 * stdev) + 5  # media + 2σ + 5s margen
            else:
                recommended = int(statistics.mean(times)) + 10
            recommendations[plugin] = max(15, min(recommended, 300))  # mínimo 15s, máximo 5min

        return recommendations

    # ── 2. Recomendación de estrategias ──

    def recommended_strategies(self) -> dict[str, str]:
        """Recomienda la estrategia con mejor tasa de éxito por tipo de objetivo.

        Analiza el ledger histórico para determinar qué estrategia
        funcionó mejor para cada tipo de objetivo.
        """
        entries = self._load_entries()
        strategy_results: dict[str, list[bool]] = {}

        for e in entries:
            plan = e.get("plan") or {}
            strategy = plan.get("strategy", "unknown")
            promotion = e.get("promotion", False)
            strategy_results.setdefault(strategy, []).append(promotion)

        recommendations = {}
        for strategy, results in strategy_results.items():
            if len(results) >= 2:
                success_rate = sum(results) / len(results)
                recommendations[strategy] = (
                    "recomendada" if success_rate >= 0.8 else
                    "usar_con_cautela" if success_rate >= 0.5 else
                    "evitar"
                )
        return recommendations

    # ── 3. Detección de regresiones ──

    def detect_regressions(self) -> list[dict[str, Any]]:
        """Detecta plugins que están tardando más de lo histórico.

        Si un plugin tarda 3x más que su media histórica, se reporta
        como regresión para que el planificador lo considere.
        """
        entries = self._load_entries()
        if len(entries) < 3:
            return []

        plugin_times: dict[str, list[float]] = {}
        for e in entries[:-1]:  # excluir la última (actual)
            for p, d in e.get("plugin_durations", {}).items():
                plugin_times.setdefault(p, []).append(d)

        last = entries[-1]
        regressions = []
        for p, d in last.get("plugin_durations", {}).items():
            historical = plugin_times.get(p, [])
            if len(historical) >= 2:
                avg = statistics.mean(historical)
                if d > avg * 3 and d > 10:
                    regressions.append({
                        "plugin": p,
                        "actual_s": round(d, 1),
                        "historical_avg_s": round(avg, 1),
                        "ratio": round(d / avg, 1),
                        "recommendation": "revisar_timeout_o_herramienta",
                    })
        return regressions

    # ── 4. Sugerencia de plugins a omitir ──

    def skip_recommendations(self) -> list[str]:
        """Sugiere plugins que deberían omitirse por fallos recurrentes.

        Si un plugin falla en >50% de las ejecuciones, se recomienda
        omitirlo hasta que sea reparado.
        """
        entries = self._load_entries()
        plugin_fails: dict[str, list[bool]] = {}

        for e in entries:
            for p, s in e.get("plugin_status", {}).items():
                plugin_fails.setdefault(p, []).append(s == "ok")

        to_skip = []
        for plugin, results in plugin_fails.items():
            if len(results) >= 3:
                success_rate = sum(results) / len(results)
                if success_rate < 0.5:
                    to_skip.append(plugin)
        return to_skip

    # ── 5. Métricas históricas (análisis original) ──

    def analyze(self) -> dict[str, Any]:
        """Analiza el historial completo. Retorna métricas + recomendaciones."""
        entries = self._load_entries()
        if not entries:
            return {"error": "no ledger data", "total": 0}

        total = len(entries)
        promoted = sum(1 for e in entries if e.get("promotion"))
        durations = [e.get("duration_ms", 0) for e in entries if e.get("duration_ms")]

        timeouts = self.recommended_timeouts()
        strategies = self.recommended_strategies()
        regressions = self.detect_regressions()
        to_skip = self.skip_recommendations()

        result = {
            "total_ejecuciones": total,
            "tasa_promocion": round(promoted / total, 2) if total else 0,
            "duracion_media_s": round(sum(durations) / len(durations) / 1000, 1) if durations else 0,
            "acciones_generadas": {
                "timeouts_recomendados": len(timeouts),
                "estrategias_evaluadas": len(strategies),
                "regresiones_detectadas": len(regressions),
                "plugins_a_omitir": len(to_skip),
            },
        }

        if timeouts:
            # Mostrar principales ajustes
            top_adjustments = sorted(timeouts.items(), key=lambda x: -x[1])[:5]
            result["ajustes_destacados"] = [
                f"{p}: {v}s" for p, v in top_adjustments
            ]

        if strategies:
            result["estrategias"] = strategies

        if regressions:
            result["regresiones"] = regressions[:3]

        if to_skip:
            result["plugins_a_omitir"] = to_skip

        # Registrar aprendizaje en el ledger
        self._engine.ledger.add_decision("learning_completed", {
            "timeouts_ajustados": len(timeouts),
            "regresiones": len(regressions),
            "plugins_a_omitir": to_skip,
        })

        return result

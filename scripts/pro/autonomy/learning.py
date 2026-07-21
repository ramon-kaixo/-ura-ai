"""Learning Plugin v3.5 — aprendizaje con efecto observable.

Usa LedgerValidator compartido (elimina duplicación D1).
Timeouts con límite superior (fix D5).
"""

from __future__ import annotations

import statistics
from typing import TYPE_CHECKING, Any

from scripts.pro.autonomy.learning.ledger_utils import LedgerValidator

if TYPE_CHECKING:
    from scripts.pro.tuneladora.engine import PipelineEngine


class LearningPlugin:
    """Aprendizaje útil: ajusta comportamiento futuro basado en histórico."""

    def __init__(self, engine: PipelineEngine) -> None:
        self._engine = engine
        self._validator = LedgerValidator(engine.config.nervioso)

    @property
    def ledger_stats(self) -> dict:
        return self._validator.stats

    def _entries(self) -> list[dict]:
        return self._validator.load()

    def recommended_timeouts(self) -> dict[str, int]:
        """Recomienda timeouts basados en duración histórica (media + 2σ)."""
        entries = self._entries()
        plugin_times: dict[str, list[float]] = {}
        for e in entries:
            for p, d in (e.get("plugin_durations") or {}).items():
                plugin_times.setdefault(p, []).append(d)

        recommendations = {}
        for plugin, times in plugin_times.items():
            if len(times) >= 2:
                avg = statistics.mean(times)
                stdev = statistics.stdev(times) if len(times) > 1 else avg * 0.5
                recommended = int(avg + 2 * stdev) + 5
            else:
                recommended = int(statistics.mean(times)) + 10
            recommendations[plugin] = max(15, min(recommended, 300))
        return recommendations

    def recommended_strategies(self) -> dict[str, str]:
        """Recomienda estrategia con mejor tasa de éxito histórica."""
        entries = self._entries()
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
                    "recomendada" if success_rate >= 0.8 else "usar_con_cautela" if success_rate >= 0.5 else "evitar"
                )
        return recommendations

    def detect_regressions(self) -> list[dict[str, Any]]:
        """Detecta plugins que están tardando más de lo histórico (3x+)."""
        entries = self._entries()
        if len(entries) < 3:
            return []

        plugin_times: dict[str, list[float]] = {}
        for e in entries[:-1]:
            for p, d in (e.get("plugin_durations") or {}).items():
                plugin_times.setdefault(p, []).append(d)

        last = entries[-1]
        regressions = []
        for p, d in (last.get("plugin_durations") or {}).items():
            historical = plugin_times.get(p, [])
            if len(historical) >= 2:
                avg = statistics.mean(historical)
                if d > avg * 3 and d > 10:
                    regressions.append(
                        {
                            "plugin": p,
                            "actual_s": round(d, 1),
                            "historical_avg_s": round(avg, 1),
                            "ratio": round(d / avg, 1),
                            "recommendation": "revisar_timeout_o_herramienta",
                        }
                    )
        return regressions

    def skip_recommendations(self) -> list[str]:
        """Sugiere plugins a omitir por fallos recurrentes (>50%)."""
        entries = self._entries()
        plugin_fails: dict[str, list[bool]] = {}
        for e in entries:
            for p, s in (e.get("plugin_status") or {}).items():
                plugin_fails.setdefault(p, []).append(s == "ok")

        to_skip = []
        for plugin, results in plugin_fails.items():
            if len(results) >= 3:
                success_rate = sum(results) / len(results)
                if success_rate < 0.5:
                    to_skip.append(plugin)
        return to_skip

    def analyze(self) -> dict[str, Any]:
        """Analiza el historial completo. Retorna métricas + recomendaciones."""
        entries = self._entries()
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
            "calidad_datos": self._validator.stats,
        }

        if timeouts:
            top_adjustments = sorted(timeouts.items(), key=lambda x: -x[1])[:5]
            result["ajustes_destacados"] = [f"{p}: {v}s" for p, v in top_adjustments]
        if strategies:
            result["estrategias"] = strategies
        if regressions:
            result["regresiones"] = regressions[:3]
        if to_skip:
            result["plugins_a_omitir"] = to_skip

        self._engine.ledger.add_decision(
            "learning_completed",
            {
                "timeouts_ajustados": len(timeouts),
                "regresiones": len(regressions),
                "plugins_a_omitir": to_skip,
                "ledger_stats": self._validator.stats,
            },
        )
        return result

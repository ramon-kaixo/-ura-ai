"""RecommendationEngine — transforma patrones en recomendaciones.

Cada recomendación tiene:
  evidencia (datos que la sustentan)
  confianza (0-1)
  impacto esperado (bajo/medio/alto)
  riesgo (bajo/medio/alto)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from scripts.pro.autonomy.learning.knowledge_base import KnowledgeBase
    from scripts.pro.autonomy.learning.pattern_analyzer import PatternAnalyzer


class RecommendationEngine:
    """Genera recomendaciones accionables desde patrones y conocimiento."""

    def __init__(self, analyzer: PatternAnalyzer, kb: KnowledgeBase) -> None:
        self._analyzer = analyzer
        self._kb = kb

    def generate(self) -> list[dict[str, Any]]:
        """Analiza patrones y conocimiento. Retorna recomendaciones priorizadas."""
        patterns = self._analyzer.analyze()
        recommendations: list[dict[str, Any]] = []

        for pattern in patterns:
            rec = self._pattern_to_recommendation(pattern)
            if rec:
                recommendations.append(rec)

        # Añadir recomendaciones desde conocimiento no verificado
        recommendations.extend(
            {
                "id": f"rec_{k['id']}",
                "title": k["claim"],
                "evidence": k["evidence"],
                "confidence": k["confidence"],
                "impact": "medium",
                "risk": "low",
                "source": "knowledge_base",
                "policy": "revisar_timeout" if "tiempo" in k.get("claim", "") else "revisar_config",
            }
            for k in self._kb.search(min_confidence=0.7)
            if not k.get("verified")
        )

        recommendations.sort(key=lambda r: {"high": 0, "medium": 1, "low": 2}.get(r.get("impact", "low"), 99))
        return recommendations

    def _pattern_to_recommendation(self, pattern: dict) -> dict | None:
        pname = pattern.get("pattern", "")

        if "plugin_fail" in pname:
            plugin = pname.replace("plugin_fail_", "")
            return {
                "id": f"rec_{pname}",
                "title": f"Revisar plugin {plugin}",
                "evidence": f"Falla {pattern.get('tasa_fallo', 0) * 100}% de las veces ({pattern.get('occurrences', 0)}/{pattern.get('total_ejecuciones', 0)})",
                "confidence": 1.0 - pattern.get("tasa_fallo", 0),
                "impact": "high" if pattern.get("severity") == "high" else "medium",
                "risk": "low",
                "source": "pattern_analyzer",
                "policy": "deshabilitar_temporalmente" if pattern.get("severity") == "high" else "revisar_config",
            }

        if "phase_slow" in pname:
            phase = pname.replace("phase_slow_", "")
            return {
                "id": f"rec_{pname}",
                "title": f"Aumentar timeout de fase {phase}",
                "evidence": f"Picos de {pattern.get('max_s', 0)}s contra media de {pattern.get('avg_s', 0)}s",
                "confidence": 0.7,
                "impact": "medium",
                "risk": "low",
                "source": "pattern_analyzer",
                "policy": "aumentar_timeout",
            }

        if "goal_fail" in pname:
            title = pname.replace("goal_fail_", "")
            return {
                "id": f"rec_{pname}",
                "title": f"Revisar objetivo '{title}'",
                "evidence": f"Tasa de fallo del {pattern.get('tasa_fallo', 0) * 100}%",
                "confidence": 0.6,
                "impact": "medium",
                "risk": "medium",
                "source": "pattern_analyzer",
                "policy": "dividir_objetivo",
            }

        return None

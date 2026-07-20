"""SynthesisEngine — sintetiza conclusiones a partir de evidencias.

Toma una hipótesis + evidencias y genera una conclusión estructurada.
"""

from __future__ import annotations

from typing import Any


class SynthesisEngine:
    """Sintetiza conclusiones desde hipótesis y evidencias."""

    def synthesize(self, hypothesis: dict, evidence: list[dict]) -> dict[str, Any]:
        """Evalúa hipótesis con evidencias. Retorna conclusión."""
        apoyan = sum(1 for e in evidence if e.get("tipo") == "apoya")
        contradicen = sum(1 for e in evidence if e.get("tipo") == "contradice")
        total = len(evidence)

        if total == 0:
            return {
                "hypothesis_id": hypothesis.get("id"),
                "veredicto": "sin_datos",
                "confianza": 0.0,
                "conclusion": f"No hay suficientes datos para evaluar: {hypothesis.get('claim', '')}",
                "apoyan": 0,
                "contradicen": 0,
            }

        ratio = apoyan / total if total else 0
        if ratio >= 0.7:
            veredicto = "confirmada"
            confianza = ratio
        elif ratio >= 0.3:
            veredicto = "no_concluyente"
            confianza = ratio
        else:
            veredicto = "refutada"
            confianza = 1 - ratio

        conclusiones = {
            "confirmada": f"Los datos confirman que {hypothesis.get('claim', '')}",
            "no_concluyente": f"Los datos son insuficientes para determinar si {hypothesis.get('claim', '')}",
            "refutada": f"Los datos contradicen que {hypothesis.get('claim', '')}",
            "sin_datos": f"No hay datos para evaluar la hipótesis",
        }

        return {
            "hypothesis_id": hypothesis.get("id"),
            "title": hypothesis.get("title"),
            "veredicto": veredicto,
            "confianza": round(confianza, 2),
            "conclusion": conclusiones.get(veredicto, ""),
            "apoyan": apoyan,
            "contradicen": contradicen,
            "total_evidencias": total,
        }

"""SynthesisEngine — sintetiza conclusiones y las verifica contra datos posteriores.

Flujo completo: Hipótesis → Evidencias → Síntesis → Verificación
"""

from __future__ import annotations

from typing import Any


class SynthesisEngine:
    """Sintetiza conclusiones desde hipótesis y evidencias, y las verifica."""

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
            "sin_datos": "No hay datos para evaluar la hipótesis",
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
            "requiere_verificacion": veredicto == "confirmada",
            "verificada": False,
        }

    def verify(self, conclusion: dict, new_evidence: list[dict]) -> dict:
        """Verifica una conclusión con nuevos datos.

        Si los nuevos datos contradicen la conclusión anterior,
        se marca como 'desactualizada' y se reduce la confianza.
        """
        if not conclusion.get("requiere_verificacion"):
            return {**conclusion, "verificada": True, "verificada_en": "sin_cambio"}

        apoyan = sum(1 for e in new_evidence if e.get("tipo") == "apoya")
        sum(1 for e in new_evidence if e.get("tipo") == "contradice")
        total = len(new_evidence)

        if total == 0:
            return {**conclusion, "verificada": True, "verificada_en": "sin_datos_nuevos"}

        ratio = apoyan / total
        if ratio >= 0.5:
            return {
                **conclusion,
                "verificada": True,
                "verificada_en": "confirmada",
                "confianza": round((conclusion.get("confianza", 0) + ratio) / 2, 2),
            }
        else:
            return {
                **conclusion,
                "veredicto": "desactualizada",
                "confianza": round(conclusion.get("confianza", 0) * 0.5, 2),
                "conclusion": f"La conclusión anterior ya no es válida con los nuevos datos ({conclusion.get('title', '')})",
                "verificada": True,
                "verificada_en": "contradicha",
            }

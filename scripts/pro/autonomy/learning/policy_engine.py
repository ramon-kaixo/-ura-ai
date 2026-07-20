"""PolicyEngine — decide qué hacer con las recomendaciones.

Modos:
  observación: solo informa, no aplica cambios
  asistido: propone cambios, requiere aprobación
  autónomo: aplica políticas permitidas automáticamente

Verificación: toda política aplicada se comprueba tras N ejecuciones.
"""

from __future__ import annotations

from typing import Any

from scripts.pro.autonomy.learning.knowledge_base import KnowledgeBase
from scripts.pro.autonomy.learning.trend_monitor import TrendMonitor


class PolicyEngine:
    """Motor de políticas: decide aplicar, diferir o rechazar recomendaciones."""

    def __init__(self, kb: KnowledgeBase, monitor: TrendMonitor, mode: str = "observacion") -> None:
        self._kb = kb
        self._monitor = monitor
        self.mode = mode
        self._applied: list[dict] = []
        self._allowed_policies: set[str] = {"aumentar_timeout", "revisar_timeout"}

    def evaluate(self, recommendation: dict) -> dict:
        """Evalúa una recomendación y decide acción según el modo."""
        policy = recommendation.get("policy", "")
        risk = recommendation.get("risk", "medium")
        confidence = recommendation.get("confidence", 0.5)

        if self.mode == "observacion":
            return {
                "recommendation_id": recommendation.get("id"),
                "action": "informar",
                "reason": "modo observación — no se aplican cambios automáticos",
                "applied": False,
            }

        if self.mode == "asistido":
            return {
                "recommendation_id": recommendation.get("id"),
                "action": "proponer",
                "reason": f"Recomendación: {recommendation.get('title')}. "
                         f"Confianza: {confidence}. Impacto: {recommendation.get('impact')}. "
                         f"Riesgo: {risk}. Aprobar con --policy-accept {recommendation.get('id')}",
                "applied": False,
            }

        # Modo autónomo
        if policy in self._allowed_policies and risk != "high":
            self._apply_policy(recommendation)
            return {
                "recommendation_id": recommendation.get("id"),
                "action": "aplicar",
                "policy": policy,
                "reason": f"Política '{policy}' aplicada automáticamente",
                "applied": True,
            }

        return {
            "recommendation_id": recommendation.get("id"),
            "action": "rechazar",
            "reason": f"Política '{policy}' no permitida en modo autónomo o riesgo alto",
            "applied": False,
        }

    def _apply_policy(self, recommendation: dict) -> None:
        entry = {
            "recommendation_id": recommendation.get("id"),
            "title": recommendation.get("title"),
            "policy": recommendation.get("policy"),
            "applied_at": __import__("datetime").datetime.now(__import__("datetime").UTC).isoformat(),
        }
        self._applied.append(entry)
        self._monitor.register_policy(entry)

        # Registrar en knowledge base
        self._kb.add(
            claim=f"Política aplicada: {recommendation.get('title')}",
            evidence=f"Recomendación {recommendation.get('id')} aplicada en modo autónomo",
            confidence=recommendation.get("confidence", 0.5),
            category="politica",
            source="policy_engine",
        )

    def verify_policies(self) -> list[dict]:
        """Verifica políticas aplicadas anteriormente.

        Compara métricas antes/después para cada política.
        """
        results = []
        for policy in self._monitor.get_pending_verification():
            before, after = self._monitor.compare_before_after(policy)
            improved = after < before * 0.8 if after else False
            results.append({
                "policy_id": policy.get("recommendation_id"),
                "before": before,
                "after": after,
                "improved": improved,
                "action": "confirmar" if improved else "rollback",
            })
            if improved:
                k = self._kb.search(category="politica")
                for entry in k:
                    if policy.get("title", "") in entry.get("claim", ""):
                        self._kb.verify(entry["id"], True)
        return results

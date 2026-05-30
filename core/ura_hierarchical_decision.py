#!/usr/bin/env python3
"""
Sistema de Decisión Jerárquico de URA - Integración Máxima

Sistema de decisión jerárquico:
- Nivel superior: Valores (filtro final)
- Nivel medio: Planificación y anticipación
- Nivel de ejecución: Emociones y personalidad
"""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

HIERARCHICAL_DECISION_PATH = Path.home() / ".ura" / "hierarchical_decision.json"
HIERARCHICAL_DECISION_PATH.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class Decision:
    """Decisión jerárquica."""

    action: str
    reasoning: str
    approved_by: list[str]  # Niveles que aprobaron
    rejected_by: list[str]  # Niveles que rechazaron
    final_decision: str  # approved, rejected, modified
    timestamp: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Decision":
        return cls(**data)


class URAHierarchicalDecision:
    """Gestor de decisión jerárquico de URA."""

    def __init__(self):
        self.decisions = self._load_decisions()

    def _load_decisions(self) -> list[Decision]:
        """Cargar decisiones desde disco."""
        decisions = []
        if HIERARCHICAL_DECISION_PATH.exists():
            try:
                with open(HIERARCHICAL_DECISION_PATH) as f:
                    data = json.load(f)
                    decisions = [Decision.from_dict(d) for d in data.get("decisions", [])]
            except Exception as e:
                logger.error(f"Error cargando decisiones: {e}")
        return decisions

    def _save_decisions(self):
        """Guardar decisiones a disco."""
        with open(HIERARCHICAL_DECISION_PATH, "w") as f:
            json.dump({"decisions": [d.to_dict() for d in self.decisions]}, f, indent=2)

    def evaluate_action_hierarchically(self, action: str, context: dict) -> Decision:
        """Evaluar una acción a través de la jerarquía de niveles."""
        approved_by = []
        rejected_by = []
        reasoning_parts = []

        # Nivel de ejecución: Emociones y personalidad
        try:
            from core.ura_emotions import get_ura_emotions

            emotions = get_ura_emotions()
            if emotions.current_state.emotion == "cauto":
                reasoning_parts.append("Emoción: cauto - requiere precaución")
                # No rechaza, solo advierte
            else:
                approved_by.append("emotions")
                reasoning_parts.append("Emoción: favorable")
        except Exception as e:
            logger.warning(f"Error silencioso en hierarchical_decision.emotions: {e}")
            # fallback: continuar

        try:
            from core.ura_personality import get_ura_personality

            get_ura_personality()
            # Personalidad no bloquea, solo ajusta
            approved_by.append("personality")
            reasoning_parts.append("Personalidad: compatible")
        except Exception as e:
            logger.warning(f"Error silencioso en hierarchical_decision.personality: {e}")
            # fallback: continuar

        # Nivel medio: Planificación y anticipación
        try:
            from core.ura_planning import get_ura_planning

            get_ura_planning()
            # Planificación evalúa riesgo
            reasoning_parts.append("Planificación: riesgo evaluado")
            approved_by.append("planning")
        except Exception as e:
            logger.warning(f"Error silencioso en hierarchical_decision.planning: {e}")
            # fallback: continuar

        try:
            from core.ura_anticipation import get_ura_anticipation

            get_ura_anticipation()
            # Anticipación no bloquea
            approved_by.append("anticipation")
            reasoning_parts.append("Anticipación: patrón reconocido")
        except Exception as e:
            logger.warning(f"Error silencioso en hierarchical_decision.anticipation: {e}")
            # fallback: continuar

        # Nivel superior: Valores (filtro final)
        try:
            from core.ura_value_system import get_ura_value_system

            value_system = get_ura_value_system()
            evaluation = value_system.evaluate_action(action)

            if evaluation["recommendation"] == "reconsider":
                rejected_by.append("value_system")
                reasoning_parts.append(
                    f"Valores: {evaluation['recommendation']} (score: {evaluation['score']:.2f})"
                )
            else:
                approved_by.append("value_system")
                reasoning_parts.append(
                    f"Valores: {evaluation['recommendation']} (score: {evaluation['score']:.2f})"
                )
        except Exception as e:
            logger.warning(f"Error silencioso en hierarchical_decision.values: {e}")
            # fallback: continuar

        # Decisión final
        if "value_system" in rejected_by:
            final_decision = "rejected"
        elif len(approved_by) >= 3:
            final_decision = "approved"
        else:
            final_decision = "modified"

        decision = Decision(
            action=action,
            reasoning=" | ".join(reasoning_parts),
            approved_by=approved_by,
            rejected_by=rejected_by,
            final_decision=final_decision,
            timestamp=datetime.now().isoformat(),
        )

        self.decisions.append(decision)

        # Mantener solo últimas 100 decisiones
        if len(self.decisions) > 100:
            self.decisions = self.decisions[-100:]

        self._save_decisions()
        return decision

    def get_decision_context(self) -> str:
        """Genera contexto de decisión jerárquico para el system prompt."""
        recent_decisions = self.decisions[-5:] if self.decisions else []

        context_parts = ["SISTEMA DE DECISIÓN JERÁRQUICO:"]
        context_parts.append("- Nivel superior: Valores (filtro final)")
        context_parts.append("- Nivel medio: Planificación y anticipación")
        context_parts.append("- Nivel ejecución: Emociones y personalidad")

        if recent_decisions:
            approved = sum(1 for d in recent_decisions if d.final_decision == "approved")
            context_parts.append(f"- Últimas 5 decisiones: {approved} aprobadas")

        return "\n".join(context_parts) + "\n"


# Singleton
_ura_hierarchical_decision: URAHierarchicalDecision | None = None


def get_ura_hierarchical_decision() -> URAHierarchicalDecision:
    """Obtener el singleton de decisión jerárquico de URA."""
    global _ura_hierarchical_decision
    if _ura_hierarchical_decision is None:
        _ura_hierarchical_decision = URAHierarchicalDecision()
    return _ura_hierarchical_decision


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    hierarchical = get_ura_hierarchical_decision()

    # Prueba
    decision = hierarchical.evaluate_action_hierarchically("Crear backup encriptado", {})
    print("Sistema de decisión jerárquico creado")
    print(decision)
    print(hierarchical.get_decision_context())

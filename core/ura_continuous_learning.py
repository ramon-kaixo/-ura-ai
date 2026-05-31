#!/usr/bin/env python3
"""
Aprendizaje Continuo de URA - Integración Máxima

Sistema de aprendizaje continuo multi-nivel:
- Cada interacción mejora al menos un nivel
- Errores activan meta-conciencia y aprendizaje por refuerzo
- Éxitos refuerzan patrones en anticipación
"""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

CONTINUOUS_LEARNING_PATH = Path.home() / ".ura" / "continuous_learning.json"
CONTINUOUS_LEARNING_PATH.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class LearningEvent:
    """Evento de aprendizaje."""

    timestamp: str
    interaction_type: str  # response, error, success, user_feedback
    levels_updated: list[str]
    learning_outcome: str
    confidence: float

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "LearningEvent":
        return cls(**data)


class URAContinuousLearning:
    """Gestor de aprendizaje continuo de URA."""

    def __init__(self):
        self.learning_events = self._load_events()
        self.learning_rate = 0.1

    def _load_events(self) -> list[LearningEvent]:
        """Cargar eventos de aprendizaje desde disco."""
        events = []
        if CONTINUOUS_LEARNING_PATH.exists():
            try:
                with open(CONTINUOUS_LEARNING_PATH) as f:
                    data = json.load(f)
                    events = [LearningEvent.from_dict(e) for e in data.get("events", [])]
            except Exception as e:
                logger.error(f"Error cargando eventos de aprendizaje: {e}")
        return events

    def _save_events(self):
        """Guardar eventos de aprendizaje a disco."""
        with open(CONTINUOUS_LEARNING_PATH, "w") as f:
            json.dump({"events": [e.to_dict() for e in self.learning_events]}, f, indent=2)


def record_interaction(self, interaction_type: str, data: dict) -> list[str]:
    """Registrar interacción y actualizar múltiples niveles."""
    levels_updated = []
    learning_outcome = ""

    try:
        hooks_triggered = trigger_hooks(interaction_type, data)
        levels_updated.extend(hooks_triggered)
    except Exception as e:
        logger.error(f"Error en hooks de retroalimentación: {e}")

    if interaction_type == "error":
        error_handling(data, levels_updated)

    elif interaction_type == "success":
        success_handling(data, levels_updated)

    elif interaction_type == "response":
        response_handling(data, levels_updated)

    event = LearningEvent(
        timestamp=datetime.now().isoformat(),
        interaction_type=interaction_type,
        levels_updated=list(set(levels_updated)),  # Eliminar duplicados
        learning_outcome=learning_outcome,
        confidence=0.7,
    )

    self.learning_events.append(event)

    if len(self.learning_events) > 500:
        self.learning_events = self.learning_events[-500:]

    self._save_events()
    return levels_updated


def trigger_hooks(interaction_type: str, data: dict) -> list[str]:
    """Triggers hooks for feedback and returns updated levels."""
    from core.ura_feedback_hooks import get_ura_feedback_hooks

    hooks = get_ura_feedback_hooks()
    triggered_hooks = hooks.trigger_hook(interaction_type, data)
    return triggered_hooks


def error_handling(data: dict, levels_updated: list[str]):
    """Handles errors by updating metaconsciousness and reinforcement learning."""
    try:
        from core.ura_metaconsciousness import get_ura_metaconsciousness

        meta = get_ura_metaconsciousness()
        if "domain" in data:
            meta.record_knowledge(data["domain"], False, data.get("error", ""))
            levels_updated.append("metaconsciousness")
    except Exception as e:
        logger.warning(f"Error silencioso en ura_continuous_learning: {e}")

    try:
        from core.ura_reinforcement_learning import get_ura_reinforcement_learning

        rl = get_ura_reinforcement_learning()
        if "action" in data:
            rl.record_outcome(data["action"], False, -0.5, data.get("error", ""))
            levels_updated.append("reinforcement_learning")
    except Exception as e:
        logger.warning(f"Error silencioso en ura_continuous_learning: {e}")


def success_handling(data: dict, levels_updated: list[str]):
    """Handles successes by updating anticipation and reinforcement learning."""
    try:
        from core.ura_anticipation import get_ura_anticipation

        anticipation = get_ura_anticipation()
        if "action" in data:
            anticipation.record_action(data["action"])
            levels_updated.append("anticipation")
    except Exception as e:
        logger.warning(f"Error silencioso en ura_continuous_learning: {e}")

    try:
        from core.ura_reinforcement_learning import get_ura_reinforcement_learning

        rl = get_ura_reinforcement_learning()
        if "action" in data:
            rl.record_outcome(data["action"], True, 0.8)
            levels_updated.append("reinforcement_learning")
    except Exception as e:
        logger.warning(f"Error silencioso en ura_continuous_learning: {e}")

    try:
        from core.ura_emotions import get_ura_emotions

        emotions = get_ura_emotions()
        emotions.set_emotion("satisfecho", 0.8, "Éxito en acción")
        levels_updated.append("emotions")
    except Exception as e:
        logger.warning(f"Error silencioso en ura_continuous_learning: {e}")


def response_handling(data: dict, levels_updated: list[str]):
    """Handles responses by updating personality and theory of mind."""
    try:
        from core.ura_personality import get_ura_personality

        personality = get_ura_personality()
        if "feedback" in data:
            personality.record_feedback(data["feedback"])
            levels_updated.append("personality")
    except Exception as e:
        logger.warning(f"Error silencioso en ura_continuous_learning: {e}")

    try:
        from core.ura_theory_of_mind import get_ura_theory_of_mind

        tom = get_ura_theory_of_mind()
        if "message" in data:
            tom.update_user_state(data["message"])
            levels_updated.append("theory_of_mind")
    except Exception as e:
        logger.warning(f"Error silencioso en ura_continuous_learning: {e}")

    def get_learning_summary(self) -> str:
        """Genera resumen de aprendizaje para el system prompt."""
        recent_events = self.learning_events[-10:] if self.learning_events else []

        if not recent_events:
            return ""

        # Contar tipos de interacciones
        interaction_counts = {}
        level_counts = {}

        for event in recent_events:
            interaction_counts[event.interaction_type] = (
                interaction_counts.get(event.interaction_type, 0) + 1
            )
            for level in event.levels_updated:
                level_counts[level] = level_counts.get(level, 0) + 1

        context_parts = ["APRENDIZAJE CONTINUO (cada interacción mejora al menos un nivel):"]
        context_parts.append(f"- Interacciones recientes: {len(recent_events)}")

        if interaction_counts:
            context_parts.append(
                f"- Tipos: {', '.join(f'{k}={v}' for k, v in interaction_counts.items())}"
            )

        if level_counts:
            top_levels = sorted(level_counts.items(), key=lambda x: x[1], reverse=True)[:3]
            context_parts.append(
                f"- Niveles más activos: {', '.join(f'{k} ({v})' for k, v in top_levels)}"
            )

        return "\n".join(context_parts) + "\n"


# Singleton
_ura_continuous_learning: URAContinuousLearning | None = None


def get_ura_continuous_learning() -> URAContinuousLearning:
    """Obtener el singleton de aprendizaje continuo de URA."""
    global _ura_continuous_learning
    if _ura_continuous_learning is None:
        _ura_continuous_learning = URAContinuousLearning()
    return _ura_continuous_learning


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    continuous = get_ura_continuous_learning()

    # Prueba
    continuous.record_interaction("success", {"action": "limpiar disco"})
    continuous.record_interaction(
        "error", {"action": "borrar archivo importante", "error": "Archivo no existe"}
    )

    print("Aprendizaje continuo creado")
    print(continuous.get_learning_summary())

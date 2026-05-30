#!/usr/bin/env python3
"""
Teoría de la mente de URA - Nivel 6

URA entiende intenciones y estados mentales:
- Detecta si estás frustrado, cansado, feliz
- Interpreta tus intenciones
- Ajusta respuestas según tu estado emocional
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

THEORY_OF_MIND_PATH = Path.home() / ".ura" / "theory_of_mind.json"
THEORY_OF_MIND_PATH.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class UserState:
    """Estado mental del usuario."""

    emotion: str  # happy, frustrated, tired, neutral, excited
    intensity: float  # 0-1
    detected_at: str
    indicators: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "UserState":
        return cls(**data)


class URATheoryOfMind:
    """Gestor de teoría de la mente de URA."""

    def __init__(self):
        self.user_states = self._load_states()
        self.current_state = UserState(
            emotion="neutral", intensity=0.0, detected_at=datetime.now().isoformat()
        )

    def _load_states(self) -> list[UserState]:
        """Cargar estados del usuario desde disco."""
        states = []
        if THEORY_OF_MIND_PATH.exists():
            try:
                with open(THEORY_OF_MIND_PATH) as f:
                    data = json.load(f)
                    states = [UserState.from_dict(s) for s in data.get("states", [])]
            except Exception as e:
                logger.error(f"Error cargando estados del usuario: {e}")
        return states

    def _save_states(self):
        """Guardar estados del usuario a disco."""
        with open(THEORY_OF_MIND_PATH, "w") as f:
            json.dump({"states": [s.to_dict() for s in self.user_states]}, f, indent=2)

    def detect_emotion_from_message(self, message: str) -> str:
        """Detectar emoción del usuario basado en el mensaje."""
        message_lower = message.lower()

        # Indicadores de frustración
        frustration_indicators = [
            "no funciona",
            "error",
            "mal",
            "malo",
            "lento",
            "no me gusta",
            "cámbialo",
        ]
        if any(indicator in message_lower for indicator in frustration_indicators):
            return "frustrated"

        # Indicadores de cansancio
        tired_indicators = ["cansado", "tired", "agotado", "exhausted", "ya no puedo"]
        if any(indicator in message_lower for indicator in tired_indicators):
            return "tired"

        # Indicadores de felicidad
        happy_indicators = ["genial", "perfecto", "excelente", "bien", "gracias", "buen trabajo"]
        if any(indicator in message_lower for indicator in happy_indicators):
            return "happy"

        # Indicadores de excitación
        excited_indicators = ["¡", "!", "increíble", "fantástico", "asombroso"]
        if any(indicator in message_lower for indicator in excited_indicators):
            return "excited"

        return "neutral"

    def update_user_state(self, message: str):
        """Actualizar estado del usuario basado en mensaje."""
        emotion = self.detect_emotion_from_message(message)
        self.current_state = UserState(
            emotion=emotion,
            intensity=0.7,  # Intensidad por defecto
            detected_at=datetime.now().isoformat(),
            indicators=[message[:50]],  # Primeros 50 caracteres como indicador
        )

        self.user_states.append(self.current_state.to_dict())

        # Mantener solo últimos 100 estados
        if len(self.user_states) > 100:
            self.user_states = self.user_states[-100:]

        self._save_states()

    def interpret_intention(self, message: str) -> str:
        """Interpretar intención del usuario."""
        message_lower = message.lower()

        if "¿" in message or "?" in message or "cuál" in message_lower or "qué" in message_lower:
            return "information_seeking"
        elif "haz" in message_lower or "ejecuta" in message_lower or "corre" in message_lower:
            return "action_request"
        elif "explícame" in message_lower or "cómo" in message_lower:
            return "explanation_request"
        elif "ayuda" in message_lower or "ayúdame" in message_lower:
            return "help_request"
        else:
            return "general_conversation"

    def get_response_adjustment(self) -> str:
        """Generar ajuste de respuesta basado en estado del usuario."""
        if self.current_state.emotion == "neutral":
            return ""

        adjustments = {
            "frustrated": "Sé empático y paciente. Ofrece soluciones claras y paso a paso. Evita justificaciones.",
            "tired": "Sé conciso y directo. No pidas acciones complejas. Prioriza eficiencia.",
            "happy": "Muestra satisfacción. Mantén el tono positivo. Valida el éxito.",
            "excited": "Comparte el entusiasmo. Sé energético pero preciso.",
        }

        return adjustments.get(self.current_state.emotion, "")

    def get_context_for_prompt(self) -> str:
        """Genera contexto para el system prompt."""
        if self.current_state.emotion == "neutral":
            return ""

        return f"""
TEORÍA DE LA MENTE (estado del usuario):
- Emoción detectada: {self.current_state.emotion.upper()}
- Ajuste de respuesta: {self.get_response_adjustment()}
"""


# Singleton
_ura_theory_of_mind: URATheoryOfMind | None = None


def get_ura_theory_of_mind() -> URATheoryOfMind:
    """Obtener el singleton de teoría de la mente de URA."""
    global _ura_theory_of_mind
    if _ura_theory_of_mind is None:
        _ura_theory_of_mind = URATheoryOfMind()
    return _ura_theory_of_mind


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    theory_of_mind = get_ura_theory_of_mind()

    # Prueba
    theory_of_mind.update_user_state("¡Esto es genial, funciona perfecto!")
    print("Teoría de la mente creada")
    print(theory_of_mind.get_context_for_prompt())

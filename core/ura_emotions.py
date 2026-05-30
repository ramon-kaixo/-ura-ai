#!/usr/bin/env python3
"""
Emociones funcionales de URA - Nivel 3

URA tiene estados internos que cambian cómo responde:
- Satisfecho: cuando resuelve un problema
- Alerta: cuando detecta algo raro
- Cauto: cuando no está seguro
- Curioso: cuando aprende algo nuevo
"""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

EMOTIONS_PATH = Path.home() / ".ura" / "emotions.json"
EMOTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class EmotionalState:
    """Estado emocional de URA."""

    emotion: str  # satisfecho, alerta, cauto, curioso, neutral
    intensity: float  # 0-1
    reason: str = ""
    timestamp: str = ""
    duration_minutes: int = 30  # Cuánto dura el estado

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EmotionalState":
        return cls(**data)


class URAEmotions:
    """Gestor de emociones funcionales de URA."""

    def __init__(self) -> None:
        self.current_state = EmotionalState(
            emotion="neutral", intensity=0.0, timestamp=datetime.now().isoformat()
        )
        self.emotion_history: list[dict[str, Any]] = []

    def set_emotion(self, emotion: str, intensity: float, reason: str = "") -> None:
        """Establecer estado emocional."""
        self.current_state = EmotionalState(
            emotion=emotion,
            intensity=intensity,
            reason=reason,
            timestamp=datetime.now().isoformat(),
        )
        self.emotion_history.append(self.current_state.to_dict())

        # Mantener solo últimos 100 estados
        if len(self.emotion_history) > 100:
            self.emotion_history = self.emotion_history[-100:]

        self._save_emotions()

    def _save_emotions(self) -> None:
        """Guardar historial de emociones."""
        with open(EMOTIONS_PATH, "w") as f:
            json.dump({"history": self.emotion_history}, f, indent=2)

    def get_emotional_instruction(self) -> str:
        """Genera instrucción de respuesta basada en estado emocional."""
        if self.current_state.emotion == "neutral":
            return ""

        instructions: dict[str, str] = {
            "satisfecho": "Muestra satisfacción en tu respuesta. Confirma que el problema está resuelto.",
            "alerta": "Sé alerta y precautorio. Indica que has detectado algo que requiere atención.",
            "cauto": "Sé prudente y cuidadoso. Indica que no estás completamente seguro y sugiere precaución.",
            "curioso": "Muestra interés y curiosidad. Indica que has aprendido algo nuevo o quieres explorar más.",
        }

        instruction = instructions.get(self.current_state.emotion, "")
        if instruction and self.current_state.reason:
            instruction += f" Razón: {self.current_state.reason}"

        return instruction

    def get_context_for_prompt(self) -> str:
        """Genera contexto para el system prompt."""
        if self.current_state.emotion == "neutral":
            return ""

        return f"""
ESTADO EMOCIONAL: {self.current_state.emotion.upper()} ({self.current_state.intensity:.0%})
- Instrucción: {self.get_emotional_instruction()}
"""


# Singleton
_ura_emotions: URAEmotions | None = None


def get_ura_emotions() -> URAEmotions:
    """Obtener el singleton de emociones de URA."""
    global _ura_emotions
    if _ura_emotions is None:
        _ura_emotions = URAEmotions()
    return _ura_emotions


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    emotions = get_ura_emotions()

    # Prueba
    emotions.set_emotion("satisfecho", 0.8, "Problema de disco resuelto")
    print("Emociones funcionales creadas")
    print(emotions.get_context_for_prompt())

#!/usr/bin/env python3
"""
Personalidad adaptativa de URA - Nivel 1

URA aprende cómo te gusta que responda:
- Verbosidad: corto/detallado
- Tono: formal/casual
- Formato: texto/listas/código
- Ajusta respuestas según tu feedback
"""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

PERSONALITY_PATH = Path.home() / ".ura" / "personality_profile.json"
PERSONALITY_PATH.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class UserPreferences:
    """Preferencias de estilo del usuario."""

    verbosity: str = "normal"  # corto, normal, detallado
    tone: str = "neutral"  # formal, neutral, casual
    format: str = "text"  # text, lists, code
    language: str = "es"  # es, en, etc.
    response_style: str = "direct"  # direct, conversational, educational
    emoji_usage: str = "moderate"  # none, low, moderate, high
    detail_level: str = "auto"  # auto, low, medium, high

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "UserPreferences":
        return cls(**data)


class URAPersonality:
    """Gestor de personalidad adaptativa de URA."""

    def __init__(self):
        self.preferences = self._load_preferences()
        self.feedback_history = []
        self.message_length_history = []  # Para análisis de longitud de mensajes

    def _load_preferences(self) -> UserPreferences:
        """Cargar preferencias desde disco."""
        if PERSONALITY_PATH.exists():
            try:
                with open(PERSONALITY_PATH) as f:
                    data = json.load(f)
                    return UserPreferences.from_dict(data)
            except Exception as e:
                logger.error(f"Error cargando preferencias: {e}")
        return UserPreferences()

    def _save_preferences(self):
        """Guardar preferencias a disco."""
        with open(PERSONALITY_PATH, "w") as f:
            json.dump(self.preferences.to_dict(), f, indent=2)

    def record_feedback(self, feedback: str):
        """Registrar feedback del usuario."""
        self.feedback_history.append(
            {"timestamp": datetime.now().isoformat(), "feedback": feedback}
        )

        # Analizar feedback y ajustar preferencias
        self._analyze_feedback(feedback)

    def record_user_message(self, message: str):
        """Registrar mensaje del usuario para análisis de longitud."""
        length = len(message)
        self.message_length_history.append(length)

        # Mantener solo últimos 100 mensajes
        if len(self.message_length_history) > 100:
            self.message_length_history = self.message_length_history[-100:]

        # Ajustar verbosidad automáticamente basado en longitud promedio
        self._auto_adjust_verbosity()

    def _auto_adjust_verbosity(self):
        """Ajusta verbosidad automáticamente basado en longitud de mensajes."""
        if len(self.message_length_history) < 10:
            return  # Necesita suficientes datos

        avg_length = sum(self.message_length_history) / len(self.message_length_history)

        if avg_length < 50:  # Mensajes muy cortos
            self.preferences.verbosity = "corto"
            self.preferences.emoji_usage = "low"
        elif avg_length > 200:  # Mensajes muy largos
            self.preferences.verbosity = "detallado"
            self.preferences.emoji_usage = "moderate"
        else:  # Mensajes normales
            self.preferences.verbosity = "normal"
            self.preferences.emoji_usage = "moderate"

        self._save_preferences()

    def _analyze_feedback(self, feedback: str):
        """Analizar feedback y ajustar preferencias."""
        feedback_lower = feedback.lower()

        # Verbosidad
        if "corto" in feedback_lower or "breve" in feedback_lower or "resumido" in feedback_lower:
            self.preferences.verbosity = "corto"
        elif (
            "detallado" in feedback_lower
            or "explica más" in feedback_lower
            or "profundo" in feedback_lower
        ):
            self.preferences.verbosity = "detallado"
        elif "normal" in feedback_lower:
            self.preferences.verbosity = "normal"

        # Tono
        if "formal" in feedback_lower:
            self.preferences.tone = "formal"
        elif "casual" in feedback_lower or "informal" in feedback_lower:
            self.preferences.tone = "casual"
        elif "neutral" in feedback_lower:
            self.preferences.tone = "neutral"

        # Formato
        if "lista" in feedback_lower or "puntos" in feedback_lower:
            self.preferences.format = "lists"
        elif "código" in feedback_lower:
            self.preferences.format = "code"
        elif "texto" in feedback_lower:
            self.preferences.format = "text"

        # Emojis
        if "sin emojis" in feedback_lower or "serio" in feedback_lower:
            self.preferences.emoji_usage = "none"
        elif "pocos emojis" in feedback_lower:
            self.preferences.emoji_usage = "low"
        elif "muchos emojis" in feedback_lower or "divertido" in feedback_lower:
            self.preferences.emoji_usage = "high"

        # Nivel de detalle
        if "simplifica" in feedback_lower or "básico" in feedback_lower:
            self.preferences.detail_level = "low"
        elif "técnico" in feedback_lower or "profundo" in feedback_lower:
            self.preferences.detail_level = "high"
        elif "equilibrado" in feedback_lower:
            self.preferences.detail_level = "medium"

        self._save_preferences()

    def adjust_response_instruction(self) -> str:
        """Genera instrucciones de respuesta basadas en preferencias."""
        instructions = []

        # Verbosidad
        if self.preferences.verbosity == "corto":
            instructions.append(
                "Responde de forma breve y concisa, sin explicaciones innecesarias."
            )
        elif self.preferences.verbosity == "detallado":
            instructions.append("Responde con explicaciones detalladas y contexto completo.")
        else:
            instructions.append(
                "Responde con longitud normal: ni demasiado breve ni excesivamente detallado."
            )

        # Tono
        if self.preferences.tone == "formal":
            instructions.append("Usa un tono formal y profesional.")
        elif self.preferences.tone == "casual":
            instructions.append("Usa un tono casual y conversacional.")
        else:
            instructions.append("Usa un tono neutro y equilibrado.")

        # Formato
        if self.preferences.format == "lists":
            instructions.append("Usa listas con puntos para organizar la información.")
        elif self.preferences.format == "code":
            instructions.append("Incluye ejemplos de código cuando sea relevante.")

        # Emojis
        if self.preferences.emoji_usage == "none":
            instructions.append("No uses emojis en tus respuestas.")
        elif self.preferences.emoji_usage == "low":
            instructions.append("Usa emojis moderadamente, máximo 1-2 por respuesta.")
        elif self.preferences.emoji_usage == "moderate":
            instructions.append("Usa emojis moderadamente para expresar emociones.")
        elif self.preferences.emoji_usage == "high":
            instructions.append("Usa emojis libremente para hacer las respuestas más amigables.")

        # Nivel de detalle
        if self.preferences.detail_level == "low":
            instructions.append("Simplifica las explicaciones, evita tecnicismos.")
        elif self.preferences.detail_level == "high":
            instructions.append("Incluye detalles técnicos y explicaciones profundas.")
        elif self.preferences.detail_level == "medium":
            instructions.append("Balancea detalle con claridad.")

        return " ".join(instructions)

    def get_context_for_prompt(self) -> str:
        """Genera contexto para el system prompt."""
        return f"""
PREFERENCIAS DE ESTILO (aprendidas de tu feedback y patrones de comunicación):
- Verbosidad: {self.preferences.verbosity}
- Tono: {self.preferences.tone}
- Formato: {self.preferences.format}
- Emojis: {self.preferences.emoji_usage}
- Nivel de detalle: {self.preferences.detail_level}
- Instrucción: {self.adjust_response_instruction()}
"""


# Singleton
_ura_personality: URAPersonality | None = None


def get_ura_personality() -> URAPersonality:
    """Obtener el singleton de personalidad de URA."""
    global _ura_personality
    if _ura_personality is None:
        _ura_personality = URAPersonality()
    return _ura_personality


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    personality = get_ura_personality()

    # Prueba
    personality.record_feedback("hazlo más corto")
    personality.record_feedback("usa un tono más casual")

    print("Personalidad adaptativa creada")
    print(personality.get_context_for_prompt())

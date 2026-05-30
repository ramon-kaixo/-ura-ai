#!/usr/bin/env python3
"""
Contexto continuo de URA - Capa 3

URA tiene contexto continuo:
- Recuerda lo que hablasteis ayer
- Sabe que llevas tres días preguntando lo mismo
- Detecta patrones en tus preguntas
- Anticipa lo que vas a necesitar
"""

import json
import logging
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

CONTEXT_DIR = Path.home() / ".ura" / "context_continuity"
CONTEXT_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class ConversationEntry:
    """Entrada de conversación."""

    timestamp: str
    user_message: str
    ura_response: str
    topic: str = ""
    intent: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ConversationEntry":
        return cls(**data)


@dataclass
class Pattern:
    """Patrón detectado en las preguntas del usuario."""

    pattern_type: str  # question_type, topic, time_of_day
    pattern_value: str
    frequency: int
    last_seen: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Pattern":
        return cls(**data)


@dataclass
class Anticipation:
    """Anticipación de necesidad del usuario."""

    anticipated_need: str
    confidence: float  # 0-1
    based_on: str  # qué patrón o historial
    suggested_action: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Anticipation":
        return cls(**data)


class ContextContinuity:
    """Contexto continuo de URA - Capa 3."""

    def __init__(self):
        self.conversations_file = CONTEXT_DIR / "conversations.jsonl"
        self.patterns_file = CONTEXT_DIR / "patterns.json"
        self.anticipations_file = CONTEXT_DIR / "anticipations.json"

        self.conversations = self._load_conversations()
        self.patterns = self._load_patterns()
        self.anticipations = self._load_anticipations()

    def _load_conversations(self) -> list[ConversationEntry]:
        """Cargar conversaciones recientes."""
        conversations = []
        if self.conversations_file.exists():
            try:
                cutoff = datetime.now() - timedelta(days=7)  # Últimos 7 días
                with open(self.conversations_file) as f:
                    for line in f:
                        if line.strip():
                            data = json.loads(line)
                            conv = ConversationEntry.from_dict(data)
                            # Solo últimos 7 días
                            if datetime.fromisoformat(conv.timestamp) >= cutoff:
                                conversations.append(conv)
            except Exception as e:
                logger.error(f"Error cargando conversaciones: {e}")
        return conversations

    def _load_patterns(self) -> list[Pattern]:
        """Cargar patrones detectados."""
        patterns = []
        if self.patterns_file.exists():
            try:
                with open(self.patterns_file) as f:
                    data = json.load(f)
                    patterns = [Pattern.from_dict(p) for p in data]
            except Exception as e:
                logger.error(f"Error cargando patrones: {e}")
        return patterns

    def _load_anticipations(self) -> list[Anticipation]:
        """Cargar anticipaciones."""
        anticipations = []
        if self.anticipations_file.exists():
            try:
                with open(self.anticipations_file) as f:
                    data = json.load(f)
                    anticipations = [Anticipation.from_dict(a) for a in data]
            except Exception as e:
                logger.error(f"Error cargando anticipaciones: {e}")
        return anticipations

    def log_conversation(
        self, user_message: str, ura_response: str, topic: str = "", intent: str = ""
    ):
        """Registrar conversación."""
        entry = ConversationEntry(
            timestamp=datetime.now().isoformat(),
            user_message=user_message,
            ura_response=ura_response,
            topic=topic,
            intent=intent,
        )
        self.conversations.append(entry)
        with open(self.conversations_file, "a") as f:
            f.write(json.dumps(entry.to_dict()) + "\n")

        # Actualizar patrones después de cada conversación
        self._update_patterns()

    def _update_patterns(self):
        """Actualizar patrones detectados."""
        # Detectar patrones en las últimas conversaciones
        recent = self.conversations[-50:]  # Últimas 50 conversaciones

        # Patrones de temas
        topics = [c.topic for c in recent if c.topic]
        topic_counter = Counter(topics)

        # Patrones de hora del día
        hours = [datetime.fromisoformat(c.timestamp).hour for c in recent]
        hour_counter = Counter(hours)

        # Patrones de tipo de pregunta
        intents = [c.intent for c in recent if c.intent]
        intent_counter = Counter(intents)

        # Actualizar patrones
        self.patterns = []

        for topic, count in topic_counter.most_common(5):
            if count >= 3:  # Mínimo 3 veces
                self.patterns.append(
                    Pattern(
                        pattern_type="topic",
                        pattern_value=topic,
                        frequency=count,
                        last_seen=datetime.now().isoformat(),
                    )
                )

        for hour, count in hour_counter.most_common(3):
            if count >= 5:  # Mínimo 5 veces
                self.patterns.append(
                    Pattern(
                        pattern_type="time_of_day",
                        pattern_value=f"{hour:02d}:00",
                        frequency=count,
                        last_seen=datetime.now().isoformat(),
                    )
                )

        for intent, count in intent_counter.most_common(5):
            if count >= 3:  # Mínimo 3 veces
                self.patterns.append(
                    Pattern(
                        pattern_type="question_type",
                        pattern_value=intent,
                        frequency=count,
                        last_seen=datetime.now().isoformat(),
                    )
                )

        self._save_patterns()

    def generate_anticipations(self):
        """Generar anticipaciones basadas en patrones."""
        self.anticipations = []

        # Anticipar basado en hora del día
        current_hour = datetime.now().hour
        for pattern in self.patterns:
            if pattern.pattern_type == "time_of_day":
                pattern_hour = int(pattern.pattern_value.split(":")[0])
                # Si la hora actual está cerca del patrón (±1 hora)
                if abs(current_hour - pattern_hour) <= 1:
                    self.anticipations.append(
                        Anticipation(
                            anticipated_need=f"Actividad habitual a las {pattern.pattern_value}",
                            confidence=0.7,
                            based_on=f"Patrón de hora: {pattern.frequency} veces",
                            suggested_action="Preparar recursos para actividad habitual",
                        )
                    )

        # Anticipar basado en temas frecuentes
        topic_patterns = [p for p in self.patterns if p.pattern_type == "topic"]
        if topic_patterns:
            top_topic = topic_patterns[0]
            self.anticipations.append(
                Anticipation(
                    anticipated_need=f"Información sobre {top_topic.pattern_value}",
                    confidence=0.6,
                    based_on=f"Patrón de tema: {top_topic.frequency} veces",
                    suggested_action=f"Tener información reciente sobre {top_topic.pattern_value}",
                )
            )

        self._save_anticipations()

    def _save_patterns(self):
        """Guardar patrones."""
        with open(self.patterns_file, "w") as f:
            json.dump([p.to_dict() for p in self.patterns], f, indent=2)

    def _save_anticipations(self):
        """Guardar anticipaciones."""
        with open(self.anticipations_file, "w") as f:
            json.dump([a.to_dict() for a in self.anticipations], f, indent=2)

    def get_conversation_summary(self, days: int = 1) -> str:
        """Obtener resumen de conversaciones de los últimos días."""
        cutoff = datetime.now() - timedelta(days=days)
        recent = [c for c in self.conversations if datetime.fromisoformat(c.timestamp) >= cutoff]

        if not recent:
            return "Sin conversaciones recientes."

        summary_parts = []
        summary_parts.append(f"{len(recent)} conversaciones en los últimos {days} días")

        # Temas principales
        topics = [c.topic for c in recent if c.topic]
        if topics:
            topic_counter = Counter(topics)
            top_topics = [f"{t} ({c})" for t, c in topic_counter.most_common(3)]
            summary_parts.append(f"Temas: {', '.join(top_topics)}")

        return " | ".join(summary_parts)

    def get_pattern_summary(self) -> str:
        """Obtener resumen de patrones."""
        if not self.patterns:
            return "Sin patrones detectados aún."

        summary_parts = []
        for pattern in self.patterns[:5]:
            summary_parts.append(
                f"{pattern.pattern_type}: {pattern.pattern_value} ({pattern.frequency}x)"
            )

        return " | ".join(summary_parts)

    def get_anticipation_summary(self) -> str:
        """Obtener resumen de anticipaciones."""
        if not self.anticipations:
            return "Sin anticipaciones activas."

        summary_parts = []
        for ant in self.anticipations[:3]:
            summary_parts.append(f"{ant.anticipated_need} ({ant.confidence:.0%})")

        return " | ".join(summary_parts)

    def get_summary_for_prompt(self) -> str:
        """Obtener resumen para el system prompt."""
        conv_summary = self.get_conversation_summary(days=1)
        pattern_summary = self.get_pattern_summary()
        anticipation_summary = self.get_anticipation_summary()

        return (
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "CONTEXTO CONTINUO\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Conversaciones: {conv_summary}\n"
            f"Patrones: {pattern_summary}\n"
            f"Anticipaciones: {anticipation_summary}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )


# Singleton
_ura_context_continuity: ContextContinuity | None = None


def get_ura_context_continuity() -> ContextContinuity:
    """Obtener el singleton de contexto continuo de URA."""
    global _ura_context_continuity
    if _ura_context_continuity is None:
        _ura_context_continuity = ContextContinuity()
    return _ura_context_continuity


# Alias para compatibilidad
def get_context_continuity() -> ContextContinuity:
    """Obtener el singleton de contexto continuo (alias de get_ura_context_continuity)."""
    return get_ura_context_continuity()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    context = get_context_continuity()

    # Prueba
    context.log_conversation(
        "¿Cómo está el disco?", "El disco tiene 33GB libres", topic="sistema", intent="consulta"
    )
    context.log_conversation(
        "¿Cuánto espacio queda?", "33GB libres", topic="sistema", intent="consulta"
    )
    context.log_conversation("¿Disk status?", "33GB libres", topic="sistema", intent="consulta")
    context.generate_anticipations()

    print("Contexto continuo creado")
    print(context.get_summary_for_prompt())

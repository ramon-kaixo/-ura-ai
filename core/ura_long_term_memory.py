#!/usr/bin/env python3
"""
Memoria a largo plazo de URA - Nivel 12

Memoria persistente de eventos a lo largo de meses/años:
- Conexiones entre eventos distantes en el tiempo
- Reconocimiento de tendencias a largo plazo
"""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

LONG_TERM_MEMORY_PATH = Path.home() / ".ura" / "long_term_memory.json"
LONG_TERM_MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class LongTermMemory:
    """Memoria a largo plazo."""

    event_id: str
    timestamp: str
    event_type: str  # conversation, error, success, pattern
    description: str
    connections: list[str]  # IDs de eventos relacionados
    importance: float  # 0-1

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "LongTermMemory":
        return cls(**data)


class URALongTermMemory:
    """Gestor de memoria a largo plazo de URA."""

    def __init__(self):
        self.memories = self._load_memories()

    def _load_memories(self) -> list[LongTermMemory]:
        """Cargar memorias desde disco."""
        memories = []
        if LONG_TERM_MEMORY_PATH.exists():
            try:
                with open(LONG_TERM_MEMORY_PATH) as f:
                    data = json.load(f)
                    memories = [LongTermMemory.from_dict(m) for m in data.get("memories", [])]
            except Exception as e:
                logger.error(f"Error cargando memorias a largo plazo: {e}")
        return memories

    def _save_memories(self):
        """Guardar memorias a disco."""
        with open(LONG_TERM_MEMORY_PATH, "w") as f:
            json.dump({"memories": [m.to_dict() for m in self.memories]}, f, indent=2)

    def record_event(self, event_type: str, description: str, importance: float = 0.5):
        """Registrar un evento en memoria a largo plazo."""
        memory = LongTermMemory(
            event_id=f"evt_{datetime.now().timestamp()}",
            timestamp=datetime.now().isoformat(),
            event_type=event_type,
            description=description,
            connections=[],
            importance=importance,
        )

        self.memories.append(memory)

        # Mantener solo últimas 1000 memorias
        if len(self.memories) > 1000:
            self.memories = self.memories[-1000:]

        self._save_memories()

    def find_trends(self, days: int = 30) -> list[str]:
        """Encontrar tendencias en los últimos N días."""
        cutoff_date = datetime.now().timestamp() - (days * 86400)
        recent_memories = [
            m
            for m in self.memories
            if datetime.fromisoformat(m.timestamp).timestamp() > cutoff_date
        ]

        # Contar tipos de eventos
        type_counts = {}
        for memory in recent_memories:
            type_counts[memory.event_type] = type_counts.get(memory.event_type, 0) + 1

        trends = []
        for event_type, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
            trends.append(f"{event_type}: {count} veces")

        return trends

    def get_long_term_context(self) -> str:
        """Genera contexto de memoria a largo plazo para el system prompt."""
        trends = self.find_trends(30)

        if not trends:
            return ""

        context_parts = ["MEMORIA A LARGO PLAZO (últimos 30 días):"]
        for trend in trends[:5]:
            context_parts.append(f"- {trend}")

        return "\n".join(context_parts) + "\n"


# Singleton
_ura_long_term_memory: URALongTermMemory | None = None


def get_ura_long_term_memory() -> URALongTermMemory:
    """Obtener el singleton de memoria a largo plazo de URA."""
    global _ura_long_term_memory
    if _ura_long_term_memory is None:
        _ura_long_term_memory = URALongTermMemory()
    return _ura_long_term_memory


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ltm = get_ura_long_term_memory()

    # Prueba
    ltm.record_event("conversation", "Usuario preguntó por estado del sistema", 0.6)
    ltm.record_event("error", "Error en backup", 0.8)

    print("Memoria a largo plazo creada")
    print(ltm.get_long_term_context())

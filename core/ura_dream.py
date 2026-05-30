#!/usr/bin/env python3
"""
Capacidad de sueño de URA - Nivel 10

URA procesa información durante el "sueño":
- Conexiones entre ideas no relacionadas
- Insight creativo durante el procesamiento nocturno
- Consolidación de aprendizaje
"""

import json
import logging
import random
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

DREAM_PATH = Path.home() / ".ura" / "dreams.json"
DREAM_PATH.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class Dream:
    """Sueño/insight generado durante procesamiento nocturno."""

    insight: str
    connections: list[str]  # Ideas conectadas
    confidence: float  # 0-1
    timestamp: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Dream":
        return cls(**data)


class URADream:
    """Gestor de capacidad de sueño de URA."""

    def __init__(self):
        self.dreams = self._load_dreams()
        self.insights_generated = []

    def _load_dreams(self) -> list[Dream]:
        """Cargar sueños desde disco."""
        dreams = []
        if DREAM_PATH.exists():
            try:
                with open(DREAM_PATH) as f:
                    data = json.load(f)
                    dreams = [Dream.from_dict(d) for d in data.get("dreams", [])]
            except Exception as e:
                logger.error(f"Error cargando sueños: {e}")
        return dreams

    def _save_dreams(self):
        """Guardar sueños a disco."""
        with open(DREAM_PATH, "w") as f:
            json.dump({"dreams": [d.to_dict() for d in self.dreams]}, f, indent=2)

    def generate_nightly_insights(self, recent_conversations: list[str]) -> list[Dream]:
        """Generar insights durante el procesamiento nocturno."""
        insights = []

        # Si no hay conversaciones recientes, generar insight aleatorio
        if not recent_conversations:
            insights.append(
                Dream(
                    insight="Revisar optimización de código para mejorar eficiencia",
                    connections=["aprendizaje", "eficiencia"],
                    confidence=0.6,
                    timestamp=datetime.now().isoformat(),
                )
            )
        else:
            # Analizar conversaciones para encontrar conexiones
            topics = self._extract_topics(recent_conversations)

            # Generar insight si hay suficientes temas
            if len(topics) >= 2:
                insight = self._generate_insight(topics)
                insights.append(
                    Dream(
                        insight=insight,
                        connections=topics[:3],
                        confidence=random.uniform(0.5, 0.8),
                        timestamp=datetime.now().isoformat(),
                    )
                )

        # Guardar nuevos insights
        self.dreams.extend(insights)

        # Mantener solo últimos 50 sueños
        if len(self.dreams) > 50:
            self.dreams = self.dreams[-50:]

        self._save_dreams()
        return insights

    def _extract_topics(self, conversations: list[str]) -> list[str]:
        """Extraer temas de conversaciones."""
        topics = []
        keywords = [
            "sistema",
            "código",
            "automatización",
            "backup",
            "seguridad",
            "eficiencia",
            "aprendizaje",
            "mejora",
            "optimización",
            "error",
            "solución",
        ]

        for conv in conversations:
            conv_lower = conv.lower()
            for keyword in keywords:
                if keyword in conv_lower and keyword not in topics:
                    topics.append(keyword)

        return topics

    def _generate_insight(self, topics: list[str]) -> str:
        """Generar insight basado en temas."""
        # Combinaciones de temas
        combinations = {
            "sistema": {
                "código": "Revisar código del sistema para optimizar rendimiento",
                "automatización": "Automatizar más tareas de mantenimiento del sistema",
                "backup": "Mejorar frecuencia de backups automáticos",
                "seguridad": "Auditar seguridad del sistema periódicamente",
            },
            "aprendizaje": {
                "mejora": "Implementar retroalimentación continua para mejorar respuestas",
                "optimización": "Optimizar algoritmos de aprendizaje para más velocidad",
            },
            "error": {
                "solución": "Crear base de conocimiento de errores y soluciones",
                "automatización": "Automatizar detección y corrección de errores comunes",
            },
        }

        # Buscar combinación
        for topic1 in topics:
            if topic1 in combinations:
                for topic2 in topics:
                    if topic2 in combinations[topic1]:
                        return combinations[topic1][topic2]

        # Fallback
        return f"Conectar {topics[0]} con {topics[1]} para mejorar eficiencia"

    def get_recent_insights(self) -> list[Dream]:
        """Obtener insights recientes."""
        return sorted(self.dreams, key=lambda x: x.timestamp, reverse=True)[:3]

    def get_dream_context(self) -> str:
        """Genera contexto de sueños para el system prompt."""
        recent_insights = self.get_recent_insights()

        if not recent_insights:
            return ""

        context_parts = ["CAPACIDAD DE SUEÑO (insights nocturnos):"]
        for dream in recent_insights:
            context_parts.append(f"- {dream.insight} (confianza: {dream.confidence:.0%})")

        return "\n".join(context_parts) + "\n"


# Singleton
_ura_dream: URADream | None = None


def get_ura_dream() -> URADream:
    """Obtener el singleton de capacidad de sueño de URA."""
    global _ura_dream
    if _ura_dream is None:
        _ura_dream = URADream()
    return _ura_dream


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    dream = get_ura_dream()

    # Prueba
    insights = dream.generate_nightly_insights(
        ["El sistema necesita más automatización", "El código podría ser más eficiente"]
    )

    print("Capacidad de sueño creada")
    print(dream.get_dream_context())

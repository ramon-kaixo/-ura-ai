#!/usr/bin/env python3
"""
Creatividad generativa de URA - Nivel 17

Generación de nuevas ideas y soluciones:
- Conexiones no obvias entre conceptos
- Innovación en resolución de problemas
"""

import json
import logging
import random
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

GENERATIVE_CREATIVITY_PATH = Path.home() / ".ura" / "generative_creativity.json"
GENERATIVE_CREATIVITY_PATH.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class CreativeIdea:
    """Idea creativa generada."""

    idea: str
    connections: list[str]  # Conceptos conectados
    novelty: float  # 0-1
    timestamp: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "CreativeIdea":
        return cls(**data)


class URAGenerativeCreativity:
    """Gestor de creatividad generativa de URA."""

    def __init__(self):
        self.ideas = self._load_ideas()
        self.concept_bank = self._create_concept_bank()

    def _load_ideas(self) -> list[CreativeIdea]:
        """Cargar ideas desde disco."""
        ideas = []
        if GENERATIVE_CREATIVITY_PATH.exists():
            try:
                with open(GENERATIVE_CREATIVITY_PATH) as f:
                    data = json.load(f)
                    ideas = [CreativeIdea.from_dict(i) for i in data.get("ideas", [])]
            except Exception as e:
                logger.error(f"Error cargando ideas creativas: {e}")
        return ideas

    def _create_concept_bank(self) -> list[str]:
        """Crear banco de conceptos."""
        return [
            "automatización",
            "seguridad",
            "eficiencia",
            "aprendizaje",
            "optimización",
            "abstracción",
            "planificación",
            "simulación",
            "creatividad",
            "reflexión",
            "memoria",
            "anticipación",
        ]

    def _save_ideas(self):
        """Guardar ideas a disco."""
        with open(GENERATIVE_CREATIVITY_PATH, "w") as f:
            json.dump({"ideas": [i.to_dict() for i in self.ideas]}, f, indent=2)

    def generate_idea(self, problem: str) -> CreativeIdea:
        """Generar idea creativa para un problema."""
        # Seleccionar 2-3 conceptos aleatorios del banco
        selected_concepts = random.sample(self.concept_bank, min(3, len(self.concept_bank)))

        # Generar idea basada en conceptos seleccionados
        idea = f"Combinar {', '.join(selected_concepts)} para resolver: {problem}"

        # Calcular novedad basada en rareza de combinación
        novelty = random.uniform(0.5, 0.9)

        creative_idea = CreativeIdea(
            idea=idea,
            connections=selected_concepts,
            novelty=novelty,
            timestamp=datetime.now().isoformat(),
        )

        self.ideas.append(creative_idea)

        # Mantener solo últimas 50 ideas
        if len(self.ideas) > 50:
            self.ideas = self.ideas[-50:]

        self._save_ideas()
        return creative_idea

    def get_creativity_context(self) -> str:
        """Genera contexto de creatividad para el system prompt."""
        recent_ideas = self.ideas[-3:] if self.ideas else []

        if not recent_ideas:
            return ""

        context_parts = ["CREATIVIDAD GENERATIVA:"]
        for idea in recent_ideas:
            context_parts.append(f"- {idea.idea[:80]}... (novedad: {idea.novelty:.0%})")

        return "\n".join(context_parts) + "\n"


# Singleton
_ura_generative_creativity: URAGenerativeCreativity | None = None


def get_ura_generative_creativity() -> URAGenerativeCreativity:
    """Obtener el singleton de creatividad generativa de URA."""
    global _ura_generative_creativity
    if _ura_generative_creativity is None:
        _ura_generative_creativity = URAGenerativeCreativity()
    return _ura_generative_creativity


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    creativity = get_ura_generative_creativity()

    # Prueba
    idea = creativity.generate_idea("Optimizar rendimiento del sistema")
    print("Creatividad generativa creada")
    print(idea)
    print(creativity.get_creativity_context())

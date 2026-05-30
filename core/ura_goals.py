#!/usr/bin/env python3
"""
Objetivos propios de URA - Nivel 4

URA tiene objetivos a largo plazo y trabaja en ellos en segundo plano:
- Mejorar su propio código
- Reducir errores
- Aprender de cada conversación
- Optimizar rendimiento
"""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

GOALS_PATH = Path.home() / ".ura" / "goals.json"
GOALS_PATH.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class Goal:
    """Objetivo a largo plazo de URA."""

    name: str
    description: str
    priority: int  # 1-10
    progress: float  # 0-1
    status: str  # active, paused, completed
    created_at: str
    updated_at: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Goal":
        return cls(**data)


class URAGoals:
    """Gestor de objetivos propios de URA."""

    def __init__(self):
        self.goals = self._load_goals()
        self.progress_history = []

    def _load_goals(self) -> list[Goal]:
        """Cargar objetivos desde disco."""
        goals = []
        if GOALS_PATH.exists():
            try:
                with open(GOALS_PATH) as f:
                    data = json.load(f)
                    goals = [Goal.from_dict(g) for g in data.get("goals", [])]
            except Exception as e:
                logger.error(f"Error cargando objetivos: {e}")

        # Si no hay objetivos, crear los por defecto
        if not goals:
            goals = self._create_default_goals()

        return goals

    def _create_default_goals(self) -> list[Goal]:
        """Crear objetivos por defecto."""
        now = datetime.now().isoformat()
        return [
            Goal(
                name="reducir_errores",
                description="Reducir errores en respuestas y comandos",
                priority=8,
                progress=0.0,
                status="active",
                created_at=now,
                updated_at=now,
            ),
            Goal(
                name="mejorar_codigo",
                description="Mejorar la calidad del código propio",
                priority=7,
                progress=0.0,
                status="active",
                created_at=now,
                updated_at=now,
            ),
            Goal(
                name="aprender_conversaciones",
                description="Aprender de cada conversación para mejorar respuestas",
                priority=6,
                progress=0.0,
                status="active",
                created_at=now,
                updated_at=now,
            ),
            Goal(
                name="optimizar_rendimiento",
                description="Optimizar rendimiento del sistema",
                priority=5,
                progress=0.0,
                status="active",
                created_at=now,
                updated_at=now,
            ),
        ]

    def _save_goals(self):
        """Guardar objetivos a disco."""
        with open(GOALS_PATH, "w") as f:
            json.dump({"goals": [g.to_dict() for g in self.goals]}, f, indent=2)

    def update_progress(self, goal_name: str, progress: float):
        """Actualizar progreso de un objetivo."""
        for goal in self.goals:
            if goal.name == goal_name:
                goal.progress = min(max(progress, 0.0), 1.0)
                goal.updated_at = datetime.now().isoformat()

                if goal.progress >= 1.0:
                    goal.status = "completed"

                self.progress_history.append(
                    {
                        "timestamp": datetime.now().isoformat(),
                        "goal": goal_name,
                        "progress": goal.progress,
                    }
                )

                self._save_goals()
                return True
        return False

    def record_learning(self, learning: str):
        """Registrar aprendizaje de una conversación."""
        # Actualizar objetivo de aprendizaje
        for goal in self.goals:
            if goal.name == "aprender_conversaciones":
                goal.progress = min(goal.progress + 0.05, 1.0)
                goal.updated_at = datetime.now().isoformat()

        self._save_goals()

    def get_active_goals(self) -> list[Goal]:
        """Obtener objetivos activos ordenados por prioridad."""
        active = [g for g in self.goals if g.status == "active"]
        return sorted(active, key=lambda x: x.priority, reverse=True)

    def get_context_for_prompt(self) -> str:
        """Generar contexto para el system prompt."""
        active_goals = self.get_active_goals()

        if not active_goals:
            return ""

        context_parts = ["OBJETIVOS PROPIOS (trabajo en segundo plano):"]
        for goal in active_goals[:3]:  # Máximo 3 objetivos
            context_parts.append(f"- {goal.description} ({goal.progress:.0%} completo)")

        return "\n".join(context_parts) + "\n"


# Singleton
_ura_goals: URAGoals | None = None


def get_ura_goals() -> URAGoals:
    """Obtener el singleton de objetivos de URA."""
    global _ura_goals
    if _ura_goals is None:
        _ura_goals = URAGoals()
    return _ura_goals


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    goals = get_ura_goals()

    # Prueba
    goals.update_progress("reducir_errores", 0.3)
    goals.record_learning("Aprendí a ser más conciso")

    print("Objetivos propios creados")
    print(goals.get_context_for_prompt())

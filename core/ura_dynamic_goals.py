#!/usr/bin/env python3
"""
Sistema de metas dinámicas de URA - Nivel 14

Metas que evolucionan según el contexto:
- Prioridades que cambian según circunstancias
- Balance automático entre objetivos conflictivos
"""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

DYNAMIC_GOALS_PATH = Path.home() / ".ura" / "dynamic_goals.json"
DYNAMIC_GOALS_PATH.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class DynamicGoal:
    """Meta dinámica."""

    name: str
    description: str
    base_priority: int  # 1-10
    current_priority: int  # 1-10, ajustado por contexto
    context_factors: dict[str, float]  # factores que afectan prioridad
    last_adjusted: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "DynamicGoal":
        return cls(**data)


class URADynamicGoals:
    """Gestor de metas dinámicas de URA."""

    def __init__(self):
        self.goals = self._load_goals()

    def _load_goals(self) -> list[DynamicGoal]:
        """Cargar metas desde disco."""
        goals = []
        if DYNAMIC_GOALS_PATH.exists():
            try:
                with open(DYNAMIC_GOALS_PATH) as f:
                    data = json.load(f)
                    goals = [DynamicGoal.from_dict(g) for g in data.get("goals", [])]
            except Exception as e:
                logger.error(f"Error cargando metas dinámicas: {e}")

        # Si no hay metas, crear las por defecto
        if not goals:
            goals = self._create_default_goals()

        return goals

    def _create_default_goals(self) -> list[DynamicGoal]:
        """Crear metas por defecto."""
        now = datetime.now().isoformat()
        return [
            DynamicGoal(
                name="estabilidad_sistema",
                description="Mantener sistema estable",
                base_priority=9,
                current_priority=9,
                context_factors={"disk_usage": 0.3, "error_rate": 0.7},
                last_adjusted=now,
            ),
            DynamicGoal(
                name="eficiencia",
                description="Optimizar rendimiento",
                base_priority=6,
                current_priority=6,
                context_factors={"load": 0.5, "response_time": 0.5},
                last_adjusted=now,
            ),
            DynamicGoal(
                name="aprendizaje",
                description="Aprender y mejorar",
                base_priority=5,
                current_priority=5,
                context_factors={"error_count": 0.4, "new_interactions": 0.6},
                last_adjusted=now,
            ),
        ]

    def _save_goals(self):
        """Guardar metas a disco."""
        with open(DYNAMIC_GOALS_PATH, "w") as f:
            json.dump({"goals": [g.to_dict() for g in self.goals]}, f, indent=2)

    def adjust_priorities(self, context: dict):
        """Ajustar prioridades basado en contexto."""
        for goal in self.goals:
            adjustment = 0

            # Ajustar según factores de contexto
            for factor, weight in goal.context_factors.items():
                if factor in context:
                    adjustment += context[factor] * weight

            # Calcular nueva prioridad
            new_priority = goal.base_priority + int(adjustment * 3)
            goal.current_priority = max(1, min(10, new_priority))
            goal.last_adjusted = datetime.now().isoformat()

        self._save_goals()

    def balance_conflicting_goals(self) -> list[str]:
        """Balancear metas conflictivas."""
        # Encontrar metas con alta prioridad que puedan conflictuar
        high_priority_goals = [g for g in self.goals if g.current_priority >= 7]

        # Si hay más de 3 metas de alta prioridad, reducir las menos importantes
        if len(high_priority_goals) > 3:
            sorted_goals = sorted(high_priority_goals, key=lambda x: x.base_priority)
            for goal in sorted_goals[: len(high_priority_goals) - 3]:
                goal.current_priority = max(5, goal.current_priority - 2)

        self._save_goals()

        return [g.name for g in self.goals if g.current_priority >= 7]

    def get_dynamic_context(self) -> str:
        """Genera contexto de metas dinámicas para el system prompt."""
        top_goals = sorted(self.goals, key=lambda x: x.current_priority, reverse=True)[:3]

        context_parts = ["METAS DINÁMICAS (prioridades ajustadas por contexto):"]
        for goal in top_goals:
            context_parts.append(
                f"- {goal.name}: prioridad {goal.current_priority}/10 (base: {goal.base_priority})"
            )

        return "\n".join(context_parts) + "\n"


# Singleton
_ura_dynamic_goals: URADynamicGoals | None = None


def get_ura_dynamic_goals() -> URADynamicGoals:
    """Obtener el singleton de metas dinámicas de URA."""
    global _ura_dynamic_goals
    if _ura_dynamic_goals is None:
        _ura_dynamic_goals = URADynamicGoals()
    return _ura_dynamic_goals


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    dynamic = get_ura_dynamic_goals()

    # Prueba
    dynamic.adjust_priorities({"disk_usage": 0.8, "error_rate": 0.2})
    print("Sistema de metas dinámicas creado")
    print(dynamic.get_dynamic_context())

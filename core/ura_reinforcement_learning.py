#!/usr/bin/env python3
"""
Aprendizaje por refuerzo de URA - Nivel 8

URA aprende de resultados de acciones:
- Qué acciones funcionaron y cuáles no
- Optimiza decisiones basándose en resultados
- Mejora continuamente sin intervención manual
"""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

REINFORCEMENT_LEARNING_PATH = Path.home() / ".ura" / "reinforcement_learning.json"
REINFORCEMENT_LEARNING_PATH.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class ActionOutcome:
    """Resultado de una acción."""

    action: str
    success: bool
    reward: float  # -1 a 1
    timestamp: str
    context: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ActionOutcome":
        return cls(**data)


class URAReinforcementLearning:
    """Gestor de aprendizaje por refuerzo de URA."""

    def __init__(self):
        self.action_outcomes = self._load_outcomes()
        self.action_values = self._calculate_action_values()

    def _load_outcomes(self) -> list[ActionOutcome]:
        """Cargar resultados de acciones desde disco."""
        outcomes = []
        if REINFORCEMENT_LEARNING_PATH.exists():
            try:
                with open(REINFORCEMENT_LEARNING_PATH) as f:
                    data = json.load(f)
                    outcomes = [ActionOutcome.from_dict(o) for o in data.get("outcomes", [])]
            except Exception as e:
                logger.error(f"Error cargando resultados de acciones: {e}")
        return outcomes

    def _save_outcomes(self):
        """Guardar resultados de acciones a disco."""
        with open(REINFORCEMENT_LEARNING_PATH, "w") as f:
            json.dump({"outcomes": [o.to_dict() for o in self.action_outcomes]}, f, indent=2)

    def _calculate_action_values(self) -> dict[str, float]:
        """Calcular valor esperado de cada acción."""
        action_values = {}

        # Agrupar por acción
        actions_dict = {}
        for outcome in self.action_outcomes:
            if outcome.action not in actions_dict:
                actions_dict[outcome.action] = []
            actions_dict[outcome.action].append(outcome)

        # Calcular valor promedio
        for action, outcomes in actions_dict.items():
            avg_reward = sum([o.reward for o in outcomes]) / len(outcomes)
            action_values[action] = avg_reward

        return action_values

    def record_outcome(self, action: str, success: bool, reward: float, context: str = ""):
        """Registrar resultado de una acción."""
        outcome = ActionOutcome(
            action=action,
            success=success,
            reward=reward,
            timestamp=datetime.now().isoformat(),
            context=context,
        )
        self.action_outcomes.append(outcome)

        # Mantener solo últimos 500 resultados
        if len(self.action_outcomes) > 500:
            self.action_outcomes = self.action_outcomes[-500:]

        # Recalcular valores
        self.action_values = self._calculate_action_values()
        self._save_outcomes()

    def get_best_action(self, possible_actions: list[str]) -> str | None:
        """Obtener mejor acción basada en valores aprendidos."""
        if not self.action_values:
            return None  # No hay datos suficientes

        # Filtrar acciones disponibles
        available_values = {k: v for k, v in self.action_values.items() if k in possible_actions}

        if not available_values:
            return None

        # Devolver acción con mayor valor
        return max(available_values, key=available_values.get)

    def get_learning_context(self) -> str:
        """Genera contexto de aprendizaje para el system prompt."""
        if not self.action_values:
            return ""

        # Top 3 acciones con mayor valor
        top_actions = sorted(self.action_values.items(), key=lambda x: x[1], reverse=True)[:3]

        context_parts = ["APRENDIZAJE POR REFUERZO (acciones aprendidas):"]
        for action, value in top_actions:
            status = "exitosa" if value > 0 else "evitar"
            context_parts.append(f"- {action}: {status} (valor: {value:.2f})")

        return "\n".join(context_parts) + "\n"


# Singleton
_ura_reinforcement_learning: URAReinforcementLearning | None = None


def get_ura_reinforcement_learning() -> URAReinforcementLearning:
    """Obtener el singleton de aprendizaje por refuerzo de URA."""
    global _ura_reinforcement_learning
    if _ura_reinforcement_learning is None:
        _ura_reinforcement_learning = URAReinforcementLearning()
    return _ura_reinforcement_learning


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    rl = get_ura_reinforcement_learning()

    # Prueba
    rl.record_outcome("limpiar disco", True, 0.8, "Éxito")
    rl.record_outcome("borrar archivo importante", False, -0.9, "Error del usuario")

    print("Aprendizaje por refuerzo creado")
    print(rl.get_learning_context())

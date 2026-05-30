#!/usr/bin/env python3
"""
Planificación a largo plazo de URA - Nivel 7

URA planifica acciones complejas multi-paso:
- Simula consecuencias antes de ejecutar
- Ajusta planes dinámicamente
- Evalúa múltiples opciones
"""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

PLANNING_PATH = Path.home() / ".ura" / "planning.json"
PLANNING_PATH.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class Action:
    """Acción individual en un plan."""

    name: str
    description: str
    estimated_duration: int  # minutos
    risk_level: str  # low, medium, high

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Action":
        return cls(**data)


@dataclass
class Plan:
    """Plan de acciones."""

    goal: str
    actions: list[Action]
    expected_outcome: str
    created_at: str
    status: str  # pending, active, completed, cancelled

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Plan":
        actions = [Action.from_dict(a) for a in data.get("actions", [])]
        return cls(
            goal=data["goal"],
            actions=actions,
            expected_outcome=data["expected_outcome"],
            created_at=data["created_at"],
            status=data["status"],
        )


class URAPlanning:
    """Gestor de planificación de URA."""

    def __init__(self):
        self.active_plans = self._load_plans()

    def _load_plans(self) -> list[Plan]:
        """Cargar planes desde disco."""
        plans = []
        if PLANNING_PATH.exists():
            try:
                with open(PLANNING_PATH) as f:
                    data = json.load(f)
                    plans = [Plan.from_dict(p) for p in data.get("plans", [])]
            except Exception as e:
                logger.error(f"Error cargando planes: {e}")
        return plans

    def _save_plans(self):
        """Guardar planes a disco."""
        with open(PLANNING_PATH, "w") as f:
            json.dump({"plans": [p.to_dict() for p in self.active_plans]}, f, indent=2)

    def create_plan(self, goal: str, actions: list[dict], expected_outcome: str) -> Plan:
        """Crear un nuevo plan."""
        action_objects = [Action(**a) for a in actions]
        plan = Plan(
            goal=goal,
            actions=action_objects,
            expected_outcome=expected_outcome,
            created_at=datetime.now().isoformat(),
            status="pending",
        )
        self.active_plans.append(plan)
        self._save_plans()
        return plan

    def simulate_consequences(self, action: Action) -> dict:
        """Simular consecuencias de una acción."""
        # Simulación simplificada
        risks = {
            "low": {"probability": 0.1, "impact": "minor"},
            "medium": {"probability": 0.3, "impact": "moderate"},
            "high": {"probability": 0.5, "impact": "severe"},
        }

        risk_info = risks.get(action.risk_level, risks["low"])

        return {
            "action": action.name,
            "risk_probability": risk_info["probability"],
            "risk_impact": risk_info["impact"],
            "estimated_time": action.estimated_duration,
            "recommendation": "proceed" if action.risk_level == "low" else "evaluate",
        }

    def evaluate_plan(self, plan: Plan) -> dict:
        """Evaluar un plan completo."""
        total_risk = sum([1 for a in plan.actions if a.risk_level == "high"])
        total_duration = sum([a.estimated_duration for a in plan.actions])

        return {
            "goal": plan.goal,
            "total_actions": len(plan.actions),
            "total_risk_actions": total_risk,
            "total_duration": total_duration,
            "recommendation": "proceed" if total_risk == 0 else "careful",
        }

    def get_context_for_prompt(self) -> str:
        """Genera contexto para el system prompt."""
        active_plans = [p for p in self.active_plans if p.status in ["pending", "active"]]

        if not active_plans:
            return ""

        context_parts = ["PLANIFICACIÓN A LARGO PLAZO (planes activos):"]
        for plan in active_plans[:2]:  # Máximo 2 planes
            evaluation = self.evaluate_plan(plan)
            context_parts.append(
                f"- {plan.goal}: {len(plan.actions)} pasos, riesgo: {evaluation['total_risk_actions']} alto"
            )

        return "\n".join(context_parts) + "\n"


# Singleton
_ura_planning: URAPlanning | None = None


def get_ura_planning() -> URAPlanning:
    """Obtener el singleton de planificación de URA."""
    global _ura_planning
    if _ura_planning is None:
        _ura_planning = URAPlanning()
    return _ura_planning


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    planning = get_ura_planning()

    # Prueba
    plan = planning.create_plan(
        goal="Limpiar disco",
        actions=[
            {
                "name": "analizar espacio",
                "description": "Analizar uso de disco",
                "estimated_duration": 5,
                "risk_level": "low",
            },
            {
                "name": "borrar caches",
                "description": "Borrar archivos cache",
                "estimated_duration": 10,
                "risk_level": "medium",
            },
        ],
        expected_outcome="Más espacio libre",
    )

    print("Planificación creada")
    print(planning.get_context_for_prompt())

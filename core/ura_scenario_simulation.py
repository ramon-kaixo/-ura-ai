#!/usr/bin/env python3
"""
Simulación de escenarios de URA - Nivel 19

Simula múltiples escenarios antes de actuar:
- Evalúa resultados potenciales de cada opción
- Elige el mejor escenario basándose en predicciones
"""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

SCENARIO_SIMULATION_PATH = Path.home() / ".ura" / "scenario_simulation.json"
SCENARIO_SIMULATION_PATH.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class Scenario:
    """Escenario simulado."""

    name: str
    action: str
    predicted_outcome: str
    success_probability: float  # 0-1
    risk_level: str  # low, medium, high
    timestamp: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Scenario":
        return cls(**data)


class URAScenarioSimulation:
    """Gestor de simulación de escenarios de URA."""

    def __init__(self):
        self.scenarios = self._load_scenarios()

    def _load_scenarios(self) -> list[Scenario]:
        """Cargar escenarios desde disco."""
        scenarios = []
        if SCENARIO_SIMULATION_PATH.exists():
            try:
                with open(SCENARIO_SIMULATION_PATH) as f:
                    data = json.load(f)
                    scenarios = [Scenario.from_dict(s) for s in data.get("scenarios", [])]
            except Exception as e:
                logger.error(f"Error cargando escenarios: {e}")
        return scenarios

    def _save_scenarios(self):
        """Guardar escenarios a disco."""
        with open(SCENARIO_SIMULATION_PATH, "w") as f:
            json.dump({"scenarios": [s.to_dict() for s in self.scenarios]}, f, indent=2)

    def simulate_scenarios(self, action: str, options: list[str]) -> list[Scenario]:
        """Simula múltiples escenarios para una acción."""
        simulated = []

        for option in options:
            # Simplificado: generar predicción basada en opción
            if "seguro" in option.lower():
                success_prob = 0.9
                risk = "low"
                outcome = f"{action} con {option}: alta probabilidad de éxito"
            elif "rápido" in option.lower():
                success_prob = 0.7
                risk = "medium"
                outcome = f"{action} con {option}: éxito moderado con riesgo"
            else:
                success_prob = 0.6
                risk = "medium"
                outcome = f"{action} con {option}: resultado incierto"

            scenario = Scenario(
                name=f"Escenario {option[:20]}",
                action=f"{action} ({option})",
                predicted_outcome=outcome,
                success_probability=success_prob,
                risk_level=risk,
                timestamp=datetime.now().isoformat(),
            )

            simulated.append(scenario)

        self.scenarios.extend(simulated)

        # Mantener solo últimos 100 escenarios
        if len(self.scenarios) > 100:
            self.scenarios = self.scenarios[-100:]

        self._save_scenarios()
        return simulated

    def select_best_scenario(self, scenarios: list[Scenario]) -> Scenario:
        """Selecciona el mejor escenario basándose en probabilidad de éxito."""
        return max(scenarios, key=lambda s: s.success_probability)

    def get_simulation_context(self) -> str:
        """Genera contexto de simulación para el system prompt."""
        recent_scenarios = self.scenarios[-3:] if self.scenarios else []

        if not recent_scenarios:
            return ""

        context_parts = ["SIMULACIÓN DE ESCENARIOS:"]
        for scenario in recent_scenarios:
            context_parts.append(
                f"- {scenario.action}: {scenario.success_probability:.0%} éxito ({scenario.risk_level} riesgo)"
            )

        return "\n".join(context_parts) + "\n"


# Singleton
_ura_scenario_simulation: URAScenarioSimulation | None = None


def get_ura_scenario_simulation() -> URAScenarioSimulation:
    """Obtener el singleton de simulación de escenarios de URA."""
    global _ura_scenario_simulation
    if _ura_scenario_simulation is None:
        _ura_scenario_simulation = URAScenarioSimulation()
    return _ura_scenario_simulation


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    simulation = get_ura_scenario_simulation()

    # Prueba
    scenarios = simulation.simulate_scenarios("Limpiar disco", ["seguro", "rápido", "completo"])
    best = simulation.select_best_scenario(scenarios)
    print("Simulación de escenarios creada")
    print(f"Mejor escenario: {best.name}")
    print(simulation.get_simulation_context())

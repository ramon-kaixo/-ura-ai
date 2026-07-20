"""AgentBase — clase base para todos los agentes del swarm.

Cada agente tiene:
  - Un nombre y dominio de especialización
  - Capacidad de recibir objetivos desde el Coordinator
  - Acceso a PipelineEngine, SemanticMemory y Research como herramientas
  - Método work(goal) que ejecuta la tarea y retorna resultados
"""

from __future__ import annotations

from typing import Any

from scripts.pro.tuneladora.engine import PipelineEngine


class AgentBase:
    """Clase base para agentes especializados."""

    def __init__(self, name: str, domain: str, engine: PipelineEngine) -> None:
        self.name = name
        self.domain = domain
        self._engine = engine

    def work(self, goal: dict) -> dict[str, Any]:
        """Ejecuta la tarea del agente. Debe ser sobrescrito."""
        raise NotImplementedError

    def log(self, msg: str) -> None:
        self._engine.log.info(f"[{self.name}] {msg}")

    def report(self, title: str, data: dict) -> None:
        self._engine.report(f"{self.name}: {title}", data)

"""Swarm — sistema multiagente coordinado.

Coordinator asigna objetivos a agentes especializados.
Cada agente usa PipelineEngine, SemanticMemory y Research como herramientas.
"""

from scripts.pro.autonomy.swarm.coordinator import Coordinator, DOMAIN_MAP
from scripts.pro.autonomy.swarm.agent_base import AgentBase
from scripts.pro.autonomy.swarm.agents import (
    ArchitectureAgent, SecurityAgent, PerformanceAgent,
    DocumentationAgent, ResearchAgent, TestingAgent,
)

__all__ = [
    "Coordinator", "AgentBase",
    "ArchitectureAgent", "SecurityAgent", "PerformanceAgent",
    "DocumentationAgent", "ResearchAgent", "TestingAgent",
]

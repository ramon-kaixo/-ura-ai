"""Swarm — sistema multiagente coordinado.

Coordinator asigna objetivos a agentes especializados.
Cada agente usa PipelineEngine, SemanticMemory y Research como herramientas.
"""

from scripts.pro.autonomy.swarm.agent_base import AgentBase
from scripts.pro.autonomy.swarm.agents import (
    ArchitectureAgent,
    DocumentationAgent,
    PerformanceAgent,
    ResearchAgent,
    SecurityAgent,
    TestingAgent,
)
from scripts.pro.autonomy.swarm.coordinator import DOMAIN_MAP, Coordinator

__all__ = [
    "AgentBase",
    "ArchitectureAgent",
    "Coordinator",
    "DocumentationAgent",
    "PerformanceAgent",
    "ResearchAgent",
    "SecurityAgent",
    "TestingAgent",
]

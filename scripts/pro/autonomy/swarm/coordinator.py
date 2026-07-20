"""Coordinator — orquestador central del swarm de agentes.

Recibe objetivos, selecciona el agente adecuado, asigna la tarea,
recoge resultados y persiste decisiones en el ExecutionLedger.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from scripts.pro.tuneladora.engine import PipelineEngine


# Mapa de dominio → agente
DOMAIN_MAP = {
    "arquitectura": "architecture",
    "deuda": "architecture",
    "refactor": "architecture",
    "seguridad": "security",
    "secrets": "security",
    "rendimiento": "performance",
    "benchmark": "performance",
    "documentacion": "documentation",
    "docs": "documentation",
    "investigacion": "research",
    "explorar": "research",
    "tests": "testing",
    "cobertura": "testing",
}


class Coordinator:
    """Coordina agentes especializados para resolver objetivos."""

    def __init__(self, engine: PipelineEngine, agents: list) -> None:
        self._engine = engine
        self._agents = {a.domain: a for a in agents}
        self._assignments: list[dict] = []

    def resolve_agent(self, goal: dict) -> str | None:
        """Determina qué agente debe manejar un objetivo según su título."""
        title = goal.get("title", "").lower()
        for keyword, domain in DOMAIN_MAP.items():
            if keyword in title:
                return domain
        return None

    def assign(self, goal: dict) -> dict[str, Any]:
        """Asigna un objetivo al agente correspondiente y ejecuta."""
        domain = self.resolve_agent(goal)
        if not domain:
            return {"error": f"No agent for goal: {goal.get('title')}", "goal_id": goal.get("goal_id")}

        agent = self._agents.get(domain)
        if not agent:
            return {"error": f"Agent '{domain}' not registered", "goal_id": goal.get("goal_id")}

        assignment = {
            "id": uuid.uuid4().hex[:8],
            "goal_id": goal["goal_id"],
            "title": goal["title"],
            "agent": agent.name,
            "domain": domain,
            "started_at": datetime.now(UTC).isoformat(),
        }
        self._assignments.append(assignment)

        self._engine.ledger.add_decision("swarm_assign", {
            "goal_id": goal["goal_id"], "agent": agent.name, "domain": domain,
        })

        try:
            result = agent.work(goal)
            assignment["result"] = result.get("status", "unknown")
            assignment["completed_at"] = datetime.now(UTC).isoformat()
        except Exception as e:
            assignment["result"] = "error"
            assignment["error"] = str(e)
            self._engine.log.warn(f"Agent {agent.name} failed: {e}")

        return dict(assignment)

    def summary(self) -> list[dict]:
        return list(self._assignments)

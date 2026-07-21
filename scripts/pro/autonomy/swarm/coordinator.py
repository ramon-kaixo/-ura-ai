"""Coordinator — orquestador central del swarm de agentes.

Recibe objetivos, selecciona agente, asigna tarea, persiste decisiones.
Incluye detección de conflictos, trazabilidad y métricas.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from scripts.pro.tuneladora.engine import PipelineEngine

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

# Áreas de impacto por dominio (para detección de conflictos)
DOMAIN_IMPACT = {
    "architecture": ["codigo", "estructura"],
    "security": ["configuracion", "permisos"],
    "performance": ["timeouts", "recursos"],
    "documentation": ["docs", "readme"],
    "research": ["conocimiento"],
    "testing": ["tests", "cobertura"],
}


class Coordinator:
    """Coordina agentes. Detecta conflictos. Traza decisiones."""

    def __init__(self, engine: PipelineEngine, agents: list) -> None:
        self._engine = engine
        self._agents = {a.domain: a for a in agents}
        self._assignments: list[dict] = []
        self._session_id = uuid.uuid4().hex[:12]
        self._metrics = {"total": 0, "ok": 0, "issues": 0, "errors": 0, "conflictos": 0}

    @property
    def session_id(self) -> str:
        return self._session_id

    def resolve_agent(self, goal: dict) -> str | None:
        title = goal.get("title", "").lower()
        for keyword, domain in DOMAIN_MAP.items():
            if keyword in title:
                return domain
        return None

    def _detect_conflict(self, new_domain: str) -> list[str]:
        """Detecta si el nuevo agente impacta áreas ya modificadas."""
        new_impact = set(DOMAIN_IMPACT.get(new_domain, []))
        conflicts = []
        for a in self._assignments:
            old_domain = a.get("domain", "")
            old_impact = set(DOMAIN_IMPACT.get(old_domain, []))
            if new_impact & old_impact and old_domain != new_domain:
                conflicts.append(old_domain)
        return conflicts

    def assign(self, goal: dict) -> dict[str, Any]:
        """Asigna objetivo a un agente. Detecta conflictos. Persiste todo."""
        domain = self.resolve_agent(goal)
        if not domain:
            return {"error": f"No agent for goal: {goal.get('title')}", "goal_id": goal.get("goal_id")}

        agent = self._agents.get(domain)
        if not agent:
            return {"error": f"Agent '{domain}' not registered", "goal_id": goal.get("goal_id")}

        # Detectar conflictos
        conflicts = self._detect_conflict(domain)
        if conflicts:
            self._metrics["conflictos"] += 1
            self._engine.log.warning(f"Conflicto potencial: {agent.name} impacta área ya modificada por {conflicts}")

        assignment = {
            "session_id": self._session_id,
            "assignment_id": uuid.uuid4().hex[:8],
            "goal_id": goal["goal_id"],
            "title": goal["title"],
            "agent": agent.name,
            "domain": domain,
            "started_at": datetime.now(UTC).isoformat(),
            "conflicts_with": conflicts,
        }
        self._assignments.append(assignment)
        self._metrics["total"] += 1

        # Persistir en ledger
        self._engine.ledger.add_decision(
            "swarm_assign",
            {
                "session_id": self._session_id,
                "goal_id": goal["goal_id"],
                "agent": agent.name,
                "domain": domain,
                "conflicts": conflicts,
            },
        )

        try:
            result = agent.work(goal)
            status = result.get("status", "unknown")
            assignment["result"] = status
            assignment["details"] = result
            assignment["completed_at"] = datetime.now(UTC).isoformat()
            self._metrics[status] = self._metrics.get(status, 0) + 1
            if status == "error":
                self._metrics["errors"] += 1
        except Exception as e:
            assignment["result"] = "error"
            assignment["error"] = str(e)
            self._metrics["errors"] += 1
            self._engine.log.warning(f"Agent {agent.name} failed: {e}")

        return dict(assignment)

    def metrics(self) -> dict:
        """Métricas del swarm: completados, conflictos, tiempo."""
        completed = [a for a in self._assignments if a.get("result") == "ok"]
        avg_time = 0
        if completed:
            times = []
            for a in completed:
                if a.get("started_at") and a.get("completed_at"):
                    try:
                        s = datetime.fromisoformat(a["started_at"])
                        e = datetime.fromisoformat(a["completed_at"])
                        times.append((e - s).total_seconds())
                    except (ValueError, TypeError):
                        pass
            avg_time = round(sum(times) / len(times), 1) if times else 0

        return {
            **self._metrics,
            "completados_ok": completed,
            "tiempo_medio_resolucion_s": avg_time,
        }

    def summary(self) -> list[dict]:
        return list(self._assignments)

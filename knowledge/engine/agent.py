"""Agent framework — agentes de conocimiento para el Knowledge Engine.

Un agente es una unidad autónoma que:
  - Recibe un objetivo (goal)
  - Consulta el grafo de conocimiento
  - Genera recomendaciones o hallazgos
  - Nunca escribe directamente en kg_*

Principios:
  - Los agentes son deterministas (mismo grafo → mismas recomendaciones).
  - Los agentes usan interfaces existentes (Reader, RuleEvaluator).
  - Los agentes no modifican el núcleo.
  - Cada agente es una implementación independiente del Protocol.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger("ura.knowledge.agent")


@dataclass(frozen=True)
class AgentGoal:
    """Objetivo asignado a un agente."""

    kind: str  # "audit" | "coverage" | "consistency" | "custom"
    description: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentFinding:
    """Hallazgo producido por un agente."""

    agent_id: str
    kind: str
    severity: str  # "INFO" | "WARN" | "ERROR"
    title: str
    description: str
    doc_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class Agent(ABC):
    """Base class para todos los agentes de conocimiento.

    Cada agente implementa execute(goal) → list[AgentFinding].
    Los agentes son stateless: toda la información viene del grafo.
    """

    @property
    @abstractmethod
    def agent_id(self) -> str:
        """Identificador único del agente."""

    @abstractmethod
    def execute(self, goal: AgentGoal) -> list[AgentFinding]:
        """Ejecuta el agente contra el grafo.

        Args:
            goal: Objetivo del agente.

        Returns:
            Lista de hallazgos.
        """


class KnowledgeGraphAgent(Agent):
    """Agente que audita la cobertura y consistencia del grafo.

    Dependencias: solo usa KnowledgeReader (no escribe, no modifica).
    """

    def __init__(self, db_path: Path):
        self._db_path = db_path
        self._id = "knowledge-graph-agent"

    @property
    def agent_id(self) -> str:
        return self._id

    def execute(self, goal: AgentGoal) -> list[AgentFinding]:
        from knowledge.engine.reader import KnowledgeReader

        reader = KnowledgeReader(db_path=self._db_path)
        findings: list[AgentFinding] = []

        if goal.kind == "audit":
            findings.extend(self._audit_coverage(reader))
        elif goal.kind == "coverage":
            findings.extend(self._check_coverage(reader, goal.params.get("doc_type", "")))
        elif goal.kind == "consistency":
            findings.extend(self._check_consistency(reader))

        return findings

    def _audit_coverage(self, reader) -> list[AgentFinding]:
        """Audita tipos de documentos y cobertura."""
        findings: list[AgentFinding] = []
        conn = reader._db_path if hasattr(reader, "_db_path") else None
        if conn is None:
            return findings

        from knowledge.engine.connection import open_db

        db_conn = open_db(self._db_path)
        rows = db_conn.execute("SELECT type, COUNT(*) as c FROM kg_nodes GROUP BY type ORDER BY c DESC").fetchall()
        db_conn.close()

        if not rows:
            findings.append(
                AgentFinding(
                    agent_id=self._id,
                    kind="audit",
                    severity="ERROR",
                    title="Grafo vacío",
                    description="No hay documentos en el grafo de conocimiento",
                )
            )
            return findings

        for row in rows:
            findings.append(
                AgentFinding(
                    agent_id=self._id,
                    kind="audit",
                    severity="INFO",
                    title=f"Tipo: {row['type']}",
                    description=f"{row['c']} documentos de tipo '{row['type']}'",
                )
            )

        return findings

    def _check_coverage(self, reader, doc_type: str) -> list[AgentFinding]:
        """Verifica cobertura de un tipo específico."""
        findings: list[AgentFinding] = []
        from knowledge.engine.connection import open_db

        db_conn = open_db(self._db_path)
        row = db_conn.execute("SELECT COUNT(*) as c FROM kg_nodes WHERE type = ?", (doc_type,)).fetchone()
        total = db_conn.execute("SELECT COUNT(*) as c FROM kg_nodes").fetchone()["c"]
        db_conn.close()

        count = row["c"] if row else 0
        if count == 0:
            findings.append(
                AgentFinding(
                    agent_id=self._id,
                    kind="coverage",
                    severity="WARN",
                    title=f"Sin documentos de tipo '{doc_type}'",
                    description=f"No hay documentos de tipo '{doc_type}' en el grafo ({total} docs totales)",
                )
            )
        else:
            findings.append(
                AgentFinding(
                    agent_id=self._id,
                    kind="coverage",
                    severity="INFO",
                    title=f"Cobertura '{doc_type}': {count}/{total}",
                    description=f"{count} documentos de tipo '{doc_type}' de {total} totales",
                )
            )
        return findings

    def _check_consistency(self, reader) -> list[AgentFinding]:
        """Verifica consistencia del grafo (edges rotos, huérfanos)."""
        from knowledge.engine.connection import open_db
        from knowledge.engine.deduction import StateDeductor

        db_conn = open_db(self._db_path)
        rows = db_conn.execute("SELECT id, type, path FROM kg_nodes").fetchall()
        edges = db_conn.execute("SELECT src, dst, relation FROM kg_edges").fetchall()
        db_conn.close()

        nodes = [dict(r) for r in rows]
        edge_list = [dict(e) for e in edges]

        deductor = StateDeductor()
        deductions = deductor.deduce(nodes, edge_list)

        findings: list[AgentFinding] = []
        for d in deductions:
            findings.append(
                AgentFinding(
                    agent_id=self._id,
                    kind=d.kind,
                    severity="WARN" if d.kind in ("orphan",) else "INFO",
                    title=f"{d.kind}: {d.subject_id}",
                    description=d.description,
                    doc_id=d.subject_id if d.kind == "orphan" else "",
                )
            )
        return findings


# ── Agent registry ────────────────────────────────────────────────────────

_AGENT_REGISTRY: dict[str, type[Agent]] = {}


def register_agent(agent_cls: type[Agent]) -> type[Agent]:
    """Registra un tipo de agente."""
    _AGENT_REGISTRY[agent_cls.__name__] = agent_cls
    return agent_cls


def list_agents() -> list[str]:
    """Lista IDs de agentes registrados."""
    return list(_AGENT_REGISTRY.keys())


def get_agent(agent_id: str, **kwargs) -> Agent | None:
    """Instancia un agente por ID."""
    cls = _AGENT_REGISTRY.get(agent_id)
    if cls is None:
        return None
    return cls(**kwargs)


# Registrar agente built-in
register_agent(KnowledgeGraphAgent)

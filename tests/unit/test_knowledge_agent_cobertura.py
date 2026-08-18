"""Tests de cobertura para knowledge/engine/agent.py."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from knowledge.engine.agent import (
    Agent,
    AgentFinding,
    AgentGoal,
    KnowledgeGraphAgent,
    get_agent,
    list_agents,
    register_agent,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS kg_nodes (
    id             TEXT PRIMARY KEY,
    type           TEXT NOT NULL,
    path           TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    frontmatter    TEXT NOT NULL,
    body           TEXT NOT NULL DEFAULT '',
    semantic       TEXT,
    quality        REAL
);
CREATE TABLE IF NOT EXISTS kg_edges (
    src      TEXT NOT NULL,
    dst      TEXT NOT NULL,
    relation TEXT NOT NULL,
    metadata TEXT,
    PRIMARY KEY (src, dst, relation)
);
"""


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "graph.db"
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    return path


def _insert(conn: sqlite3.Connection, n: int = 3) -> None:
    for i in range(n):
        conn.execute(
            "INSERT INTO kg_nodes (id, type, path, content_sha256, frontmatter) VALUES (?,?,?,?,?)",
            (f"doc{i}", "md", f"/tmp/doc{i}.md", "abc", "{}"),
        )
    conn.execute(
        "INSERT INTO kg_edges (src, dst, relation) VALUES ('doc0','doc1','links')"
    )
    conn.commit()


# ── Dataclasses ──────────────────────────────────────────────────────────


def test_agent_goal_defaults() -> None:
    g = AgentGoal(kind="custom", description="d")
    assert g.params == {}
    assert g.kind == "custom"


def test_agent_finding_defaults() -> None:
    f = AgentFinding(agent_id="a", kind="k", severity="INFO", title="t", description="d")
    assert f.doc_id == ""
    assert f.metadata == {}


def test_agent_finding_con_metadata() -> None:
    f = AgentFinding(
        agent_id="a",
        kind="k",
        severity="ERROR",
        title="t",
        description="d",
        doc_id="x",
        metadata={"k": 1},
    )
    assert f.doc_id == "x"
    assert f.metadata == {"k": 1}


def test_agent_es_abstracto() -> None:
    assert Agent.__abstractmethods__ == {"agent_id", "execute"}


# ── KnowledgeGraphAgent ──────────────────────────────────────────────────


def test_init_y_agent_id(db_path: Path) -> None:
    ag = KnowledgeGraphAgent(db_path=db_path)
    assert ag.agent_id == "knowledge-graph-agent"
    assert ag._db_path == Path(db_path)


def test_execute_custom_vacio(db_path: Path) -> None:
    ag = KnowledgeGraphAgent(db_path=db_path)
    assert ag.execute(AgentGoal(kind="custom", description="x")) == []


def test_audit_grafo_vacio(db_path: Path) -> None:
    ag = KnowledgeGraphAgent(db_path=db_path)
    findings = ag.execute(AgentGoal(kind="audit", description="a"))
    assert len(findings) == 1
    assert findings[0].severity == "ERROR"
    assert findings[0].title == "Grafo vacío"


def test_audit_reader_sin_db_path(db_path: Path) -> None:
    ag = KnowledgeGraphAgent(db_path=db_path)
    assert ag._audit_coverage(object()) == []


def test_audit_con_documentos(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    _insert(conn)
    conn.close()
    ag = KnowledgeGraphAgent(db_path=db_path)
    findings = ag.execute(AgentGoal(kind="audit", description="a"))
    assert len(findings) == 1
    assert findings[0].kind == "audit"
    assert findings[0].severity == "INFO"
    assert findings[0].title == "Tipo: md"
    assert "3" in findings[0].description


def test_coverage_sin_documentos(db_path: Path) -> None:
    ag = KnowledgeGraphAgent(db_path=db_path)
    findings = ag.execute(
        AgentGoal(kind="coverage", description="c", params={"doc_type": "md"})
    )
    assert len(findings) == 1
    assert findings[0].severity == "WARN"
    assert findings[0].title == "Sin documentos de tipo 'md'"


def test_coverage_con_documentos(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    _insert(conn)
    conn.close()
    ag = KnowledgeGraphAgent(db_path=db_path)
    findings = ag.execute(
        AgentGoal(kind="coverage", description="c", params={"doc_type": "md"})
    )
    assert len(findings) == 1
    assert findings[0].severity == "INFO"
    assert findings[0].title == "Cobertura 'md': 3/3"


def test_consistency_genera_hallazgos(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    _insert(conn)
    conn.close()
    ag = KnowledgeGraphAgent(db_path=db_path)
    findings = ag.execute(AgentGoal(kind="consistency", description="c"))
    assert findings
    kinds = {f.kind for f in findings}
    assert kinds <= {"orphan", "coverage", "hub"}
    for f in findings:
        assert f.agent_id == "knowledge-graph-agent"
        if f.kind == "orphan":
            assert f.severity == "WARN"
            assert f.doc_id


# ── Registry ─────────────────────────────────────────────────────────────


def test_registry_roundtrip() -> None:
    class DummyAgent(Agent):
        @property
        def agent_id(self) -> str:
            return "dummy"

        def execute(self, goal: AgentGoal) -> list[AgentFinding]:
            return []

    register_agent(DummyAgent)
    assert "DummyAgent" in list_agents()
    inst = get_agent("DummyAgent")
    assert isinstance(inst, DummyAgent)
    assert inst.agent_id == "dummy"
    assert get_agent("NoExiste") is None


def test_get_agent_con_kwargs(db_path: Path) -> None:
    ag = get_agent("KnowledgeGraphAgent", db_path=db_path)
    assert isinstance(ag, KnowledgeGraphAgent)
    assert ag.agent_id == "knowledge-graph-agent"


def test_builtin_registrado() -> None:
    assert "KnowledgeGraphAgent" in list_agents()

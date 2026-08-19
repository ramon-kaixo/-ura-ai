"""Tests de cobertura para knowledge/engine/cli/agent.py."""

from __future__ import annotations

import sqlite3
from argparse import Namespace
from pathlib import Path

import pytest

from knowledge.engine.cli.agent import cmd_agent_list, cmd_agent_run

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
    conn.execute(
        "INSERT INTO kg_nodes (id, type, path, content_sha256, frontmatter) VALUES ('d0','md','/x.md','abc','{}')"
    )
    conn.commit()
    conn.close()
    return path


def _args(**overrides) -> Namespace:
    base = {"db_path": None, "agent_id": "KnowledgeGraphAgent", "kind": "audit"}
    base.update(overrides)
    return Namespace(**base)


def test_list_con_agentes(capsys) -> None:
    assert cmd_agent_list(_args()) == 0
    out = capsys.readouterr().out
    assert "KnowledgeGraphAgent" in out


def test_run_audit(db_path: Path, capsys) -> None:
    rc = cmd_agent_run(_args(db_path=str(db_path)))
    assert rc == 0
    out = capsys.readouterr().out
    assert "INFO" in out
    assert "Tipo: md" in out


def test_run_agent_inexistente(db_path: Path) -> None:
    assert cmd_agent_run(_args(agent_id="NoExiste", db_path=str(db_path))) == 1


def test_run_sin_hallazgos(db_path: Path) -> None:
    assert cmd_agent_run(_args(kind="custom", db_path=str(db_path))) == 0


def test_run_warn_coverage(db_path: Path, capsys) -> None:
    rc = cmd_agent_run(_args(kind="coverage", db_path=str(db_path)))
    assert rc == 0
    out = capsys.readouterr().out
    assert "WARN" in out
    assert "Sin documentos de tipo" in out


def test_run_consistency(db_path: Path, capsys) -> None:
    rc = cmd_agent_run(_args(kind="consistency", db_path=str(db_path)))
    assert rc == 0
    assert "WARN" in capsys.readouterr().out

"""Tests de cobertura para knowledge/engine/determinism.py."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from knowledge.engine.determinism import (
    get_determinism_algorithm,
    get_determinism_hash,
    record_determinism_hash,
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
    quality        REAL,
    confidence     REAL
);
CREATE TABLE IF NOT EXISTS kg_edges (
    src      TEXT NOT NULL,
    dst      TEXT NOT NULL,
    relation TEXT NOT NULL,
    metadata TEXT,
    PRIMARY KEY (src, dst, relation)
);
CREATE TABLE IF NOT EXISTS kg_active_version (
    singleton              INTEGER PRIMARY KEY CHECK (singleton = 1),
    version_id             TEXT,
    determinism_hash       TEXT,
    determinism_algorithm  TEXT
);
"""


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "graph.db"
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    conn.execute("INSERT INTO kg_active_version (singleton) VALUES (1)")
    conn.execute(
        "INSERT INTO kg_nodes (id, type, path, content_sha256, frontmatter, body) VALUES ('d0','md','/x.md','abc','{}','cuerpo')"
    )
    conn.commit()
    conn.close()
    return path


def test_record_persiste_hash(db_path: Path) -> None:
    record_determinism_hash(db_path, run_id=42)
    h = get_determinism_hash(db_path)
    assert h is not None
    assert len(h) == 64
    algo = get_determinism_algorithm(db_path)
    assert algo == "sha256-v2"


def test_hash_estable_entre_runs(db_path: Path) -> None:
    record_determinism_hash(db_path, run_id=1)
    h1 = get_determinism_hash(db_path)
    record_determinism_hash(db_path, run_id=2)
    h2 = get_determinism_hash(db_path)
    assert h1 == h2


def test_get_hash_sin_fila() -> None:
    path = Path("/no/existe.db")
    assert get_determinism_hash(path) is None


def test_get_algorithm_error_retorna_v1() -> None:
    assert get_determinism_algorithm(Path("/no/existe.db")) == "sha256-v1"


def test_record_con_error_no_rompe() -> None:
    record_determinism_hash(Path("/no/existe.db"), run_id=3)


def test_get_algorithm_vacio_retorna_v1(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE kg_active_version SET determinism_algorithm = NULL WHERE singleton = 1")
    conn.commit()
    conn.close()
    assert get_determinism_algorithm(db_path) == "sha256-v1"

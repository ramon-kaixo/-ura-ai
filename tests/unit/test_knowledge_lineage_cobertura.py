"""Tests de cobertura para knowledge/engine/lineage_store.py."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from knowledge.engine.lineage_store import SQLiteLineageStore

SCHEMA = """
CREATE TABLE IF NOT EXISTS op_lineage (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type   TEXT NOT NULL,
    event_time   TEXT NOT NULL,
    run_id       TEXT,
    job_name     TEXT,
    namespace    TEXT,
    input_ids    TEXT NOT NULL DEFAULT '[]',
    output_ids   TEXT NOT NULL DEFAULT '[]',
    metadata     TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS op_lineage_edges (
    src         TEXT NOT NULL,
    dst         TEXT NOT NULL,
    relation    TEXT NOT NULL,
    event_id    INTEGER,
    created_at  TEXT,
    PRIMARY KEY (src, dst, relation)
);
"""

EVENT = {
    "eventType": "COMPLETE",
    "eventTime": "2026-08-19T00:00:00Z",
    "run": {"runId": "run-1"},
    "job": {"name": "compile", "namespace": "ura"},
    "inputs": [{"name": "a1"}, {"name": "a2"}],
    "outputs": [{"name": "b1"}],
    "facets": {"k": "v"},
}


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "lin.db"
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    return path


@pytest.fixture
def store(db_path: Path) -> SQLiteLineageStore:
    return SQLiteLineageStore(db_path)


def test_store_event(store, db_path) -> None:
    assert store.store_lineage_event(EVENT) is True
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    ev = conn.execute("SELECT event_type, job_name, input_ids FROM op_lineage").fetchone()
    assert ev["event_type"] == "COMPLETE"
    assert ev["job_name"] == "compile"
    assert ev["input_ids"] == '["a1", "a2"]'
    edges = conn.execute("SELECT src, dst, relation FROM op_lineage_edges").fetchall()
    conn.close()
    assert len(edges) == 2
    assert (edges[0]["src"], edges[0]["dst"]) == ("a1", "b1")


def test_store_event_sin_inputs_outputs(store) -> None:
    assert store.store_lineage_event({"eventType": "START"}) is True


def test_store_event_error(tmp_path) -> None:
    bad = SQLiteLineageStore(tmp_path / "no.db")
    assert bad.store_lineage_event(EVENT) is False


def test_get_lineage(store) -> None:
    store.store_lineage_event(EVENT)
    rows = store.get_lineage("a1")
    assert len(rows) == 1
    assert rows[0]["job_name"] == "compile"


def test_get_lineage_vacio(store) -> None:
    assert store.get_lineage("zz") == []


def test_get_lineage_error(tmp_path) -> None:
    bad = SQLiteLineageStore(tmp_path / "no.db")
    assert bad.get_lineage("a1") == []


def test_get_upstream_por_edges(store) -> None:
    store.store_lineage_event(EVENT)
    assert store.get_upstream("b1") == ["a1", "a2"]


def test_get_downstream_por_edges(store) -> None:
    store.store_lineage_event(EVENT)
    assert store.get_downstream("a1") == ["b1"]


def test_get_upstream_fallback_sin_tabla(tmp_path) -> None:
    path = tmp_path / "nolin.db"
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        "CREATE TABLE op_lineage (id INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT, event_time TEXT,"
        " run_id TEXT, job_name TEXT, namespace TEXT, input_ids TEXT, output_ids TEXT, metadata TEXT);"
    )
    conn.commit()
    conn.close()
    store = SQLiteLineageStore(path)
    store.store_lineage_event(EVENT)
    assert store.get_upstream("b1") == ["a1", "a2"]


def test_get_downstream_fallback_sin_tabla(tmp_path) -> None:
    path = tmp_path / "nolin.db"
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        "CREATE TABLE op_lineage (id INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT, event_time TEXT,"
        " run_id TEXT, job_name TEXT, namespace TEXT, input_ids TEXT, output_ids TEXT, metadata TEXT);"
    )
    conn.commit()
    conn.close()
    store = SQLiteLineageStore(path)
    store.store_lineage_event(EVENT)
    assert store.get_downstream("a1") == ["b1"]


def test_get_upstream_vacio(store) -> None:
    assert store.get_upstream("zz") == []


def test_get_downstream_vacio(store) -> None:
    assert store.get_downstream("zz") == []


def test_get_upstream_sin_tabla_ni_eventos(tmp_path) -> None:
    bad = SQLiteLineageStore(tmp_path / "no.db")
    assert bad.get_upstream("x") == []


def test_get_downstream_sin_tabla_ni_eventos(tmp_path) -> None:
    bad = SQLiteLineageStore(tmp_path / "no.db")
    assert bad.get_downstream("x") == []

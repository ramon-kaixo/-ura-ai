"""Tests de cobertura para knowledge/engine/governance_store.py."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from knowledge.engine.governance_store import SQLiteGovernanceStore

SCHEMA = """
CREATE TABLE IF NOT EXISTS op_governance (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id   TEXT NOT NULL,
    policy     TEXT NOT NULL,
    actor      TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "gov.db"
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    return path


@pytest.fixture
def store(db_path: Path) -> SQLiteGovernanceStore:
    return SQLiteGovernanceStore(db_path)


def test_set_policy(store, db_path) -> None:
    assert store.set_policy("a1", {"action": "read", "roles": ["admin"]}) is True
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT asset_id, policy, actor FROM op_governance").fetchone()
    conn.close()
    assert row["asset_id"] == "a1"
    assert "admin" in row["policy"]
    assert row["actor"] == "system"


def test_set_policy_error(tmp_path) -> None:
    bad = SQLiteGovernanceStore(tmp_path / "no.db")
    assert bad.set_policy("a1", {}) is False


def test_check_sin_politicas(store) -> None:
    assert store.check("a1", "read", "anon") is True


def test_check_rol_permitido(store) -> None:
    store.set_policy("a1", {"action": "read", "roles": ["admin", "editor"]})
    assert store.check("a1", "read", "admin") is True
    assert store.check("a1", "read", "editor") is True
    assert store.check("a1", "read", "anon") is False


def test_check_action_distinta(store) -> None:
    store.set_policy("a1", {"action": "read", "roles": ["admin"]})
    assert store.check("a1", "write", "anon") is True


def test_check_roles_vacios_continua(store) -> None:
    store.set_policy("a1", {"action": "read", "roles": []})
    store.set_policy("a1", {"action": "read", "roles": ["admin"]})
    assert store.check("a1", "read", "admin") is True


def test_check_json_invalido_continua(store, db_path) -> None:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        "INSERT INTO op_governance (asset_id, policy, actor, created_at) VALUES ('a1', 'no-json', 'x', 't')"
    )
    conn.commit()
    conn.close()
    store.set_policy("a1", {"action": "read", "roles": ["admin"]})
    assert store.check("a1", "read", "admin") is True


def test_check_error(tmp_path) -> None:
    bad = SQLiteGovernanceStore(tmp_path / "no.db")
    assert bad.check("a1", "read", "x") is True


def test_get_policies(store) -> None:
    store.set_policy("a1", {"action": "read", "roles": ["admin"]})
    rows = store.get_policies("a1")
    assert len(rows) == 1
    assert rows[0]["asset_id"] == "a1"
    assert "policy" in rows[0]


def test_get_policies_vacio(store) -> None:
    assert store.get_policies("a2") == []


def test_get_policies_error(tmp_path) -> None:
    bad = SQLiteGovernanceStore(tmp_path / "no.db")
    assert bad.get_policies("a1") == []


def test_list_policies(store) -> None:
    store.set_policy("a1", {"action": "read", "roles": ["admin"]})
    store.set_policy("a2", {"action": "delete", "roles": ["admin"]})
    rows = store.list_policies(limit=1)
    assert len(rows) == 1


def test_list_policies_error(tmp_path) -> None:
    bad = SQLiteGovernanceStore(tmp_path / "no.db")
    assert bad.list_policies() == []

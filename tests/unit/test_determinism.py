"""Tests para determinism hash (SQLite en temp dir, sin mocks)."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from knowledge.engine.determinism import (
    get_determinism_algorithm,
    get_determinism_hash,
    record_determinism_hash,
)


def _create_test_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS kg_nodes (
            id INTEGER PRIMARY KEY,
            type TEXT,
            path TEXT,
            content_sha256 TEXT,
            body TEXT,
            frontmatter TEXT DEFAULT '',
            quality REAL DEFAULT 0.0,
            confidence REAL DEFAULT 0.0
        );
        CREATE TABLE IF NOT EXISTS kg_edges (
            src INTEGER,
            dst INTEGER,
            relation TEXT,
            PRIMARY KEY (src, dst, relation)
        );
        CREATE TABLE IF NOT EXISTS kg_active_version (
            singleton INTEGER PRIMARY KEY DEFAULT 1 CHECK (singleton = 1),
            determinism_hash TEXT DEFAULT '',
            determinism_algorithm TEXT DEFAULT ''
        );
        INSERT OR IGNORE INTO kg_active_version (singleton, determinism_hash, determinism_algorithm)
        VALUES (1, '', '');
    """)
    conn.commit()
    return conn


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test_determinism.db"


def _populate_nodes(conn: sqlite3.Connection) -> None:
    conn.executemany(
        "INSERT INTO kg_nodes (id, type, path, content_sha256, body, quality, confidence) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            (1, "doc", "/docs/intro.md", "abc123", "Introduction content", 0.9, 0.95),
            (2, "doc", "/docs/api.md", "def456", "API reference", 0.8, 0.85),
        ],
    )
    conn.commit()


def _populate_edges(conn: sqlite3.Connection) -> None:
    conn.execute("INSERT INTO kg_edges (src, dst, relation) VALUES (1, 2, 'references')")
    conn.commit()


def test_record_and_get_hash_roundtrip(db_path: Path) -> None:
    conn = _create_test_db(db_path)
    _populate_nodes(conn)
    _populate_edges(conn)
    conn.close()
    record_determinism_hash(db_path, run_id=1)
    h = get_determinism_hash(db_path)
    assert h is not None
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_same_content_same_hash(db_path: Path) -> None:
    conn = _create_test_db(db_path)
    _populate_nodes(conn)
    _populate_edges(conn)
    conn.close()
    record_determinism_hash(db_path, run_id=1)
    h1 = get_determinism_hash(db_path)
    record_determinism_hash(db_path, run_id=2)
    h2 = get_determinism_hash(db_path)
    assert h1 == h2


def test_different_content_different_hash(db_path: Path) -> None:
    conn = _create_test_db(db_path)
    _populate_nodes(conn)
    _populate_edges(conn)
    conn.close()
    record_determinism_hash(db_path, run_id=1)
    h1 = get_determinism_hash(db_path)
    conn2 = _create_test_db(db_path)
    conn2.execute("UPDATE kg_nodes SET body = 'Modified content' WHERE id = 1")
    conn2.commit()
    conn2.close()
    record_determinism_hash(db_path, run_id=2)
    h2 = get_determinism_hash(db_path)
    assert h1 != h2


def test_get_hash_empty_db(db_path: Path) -> None:
    conn = _create_test_db(db_path)
    conn.close()
    h = get_determinism_hash(db_path)
    assert h == ""


def test_get_algorithm_returns_version(db_path: Path) -> None:
    conn = _create_test_db(db_path)
    _populate_nodes(conn)
    conn.close()
    record_determinism_hash(db_path, run_id=1)
    algo = get_determinism_algorithm(db_path)
    assert algo == "sha256-v2"


def test_get_algorithm_fallback_for_empty_db(db_path: Path) -> None:
    conn = _create_test_db(db_path)
    conn.close()
    algo = get_determinism_algorithm(db_path)
    assert algo == "sha256-v1"


def test_record_no_crash_on_missing_table(tmp_path: Path) -> None:
    db = tmp_path / "empty.db"
    sqlite3.connect(str(db)).close()
    record_determinism_hash(db, run_id=1)

"""Tests de cobertura para knowledge/engine/memory_store.py."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from knowledge.engine.memory_store import MemoryRecord, SQLiteMemoryStore

SCHEMA = """
CREATE TABLE IF NOT EXISTS op_memory (
    memory_id      TEXT PRIMARY KEY,
    kind           TEXT NOT NULL,
    title          TEXT NOT NULL,
    content        TEXT NOT NULL,
    related_assets TEXT NOT NULL DEFAULT '[]',
    tags           TEXT NOT NULL DEFAULT '[]',
    metadata       TEXT NOT NULL DEFAULT '{}',
    created_at     TEXT,
    updated_at     TEXT
);
CREATE VIRTUAL TABLE IF NOT EXISTS op_memory_fts USING fts5(
    id UNINDEXED, title, content, tokenize = 'unicode61'
);
CREATE TRIGGER IF NOT EXISTS op_memory_fts_ai AFTER INSERT ON op_memory BEGIN
    INSERT INTO op_memory_fts(rowid, id, title, content)
    VALUES (new.rowid, new.memory_id, new.title, new.content);
END;
CREATE TRIGGER IF NOT EXISTS op_memory_fts_ad AFTER DELETE ON op_memory BEGIN
    DELETE FROM op_memory_fts WHERE rowid = old.rowid;
END;
"""


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "mem.db"
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    return path


@pytest.fixture
def store(db_path: Path) -> SQLiteMemoryStore:
    return SQLiteMemoryStore(db_path)


def _rec(**overrides) -> MemoryRecord:
    base = {
        "memory_id": "m1",
        "kind": "decision",
        "title": "Decisión",
        "content": "Elegimos SQLite",
        "related_assets": ("a1",),
        "tags": ("db",),
        "metadata": {"severidad": "alta"},
    }
    base.update(overrides)
    return MemoryRecord(**base)


def test_record_to_dict() -> None:
    d = _rec().to_dict()
    assert d["memory_id"] == "m1"
    assert d["related_assets"] == ["a1"]
    assert d["tags"] == ["db"]
    assert d["metadata"] == {"severidad": "alta"}
    assert len(d["content"]) == len("Elegimos SQLite")


def test_record_to_dict_trunca_content() -> None:
    r = _rec(content="x" * 1000)
    assert len(r.to_dict()["content"]) == 500


def test_save_y_get(store) -> None:
    assert store.save(_rec()) is True
    got = store.get("m1")
    assert got is not None
    assert got.kind == "decision"
    assert got.title == "Decisión"
    assert got.related_assets == ("a1",)
    assert got.tags == ("db",)
    assert got.created_at  # auto-fill


def test_save_error(store, tmp_path) -> None:
    bad = SQLiteMemoryStore(tmp_path / "no.db")
    assert bad.save(_rec()) is False


def test_get_no_existe(store) -> None:
    assert store.get("nada") is None


def test_get_error(store, tmp_path) -> None:
    bad = SQLiteMemoryStore(tmp_path / "no.db")
    assert bad.get("x") is None


def test_list_sin_kind(store) -> None:
    store.save(_rec(memory_id="a"))
    store.save(_rec(memory_id="b", kind="note"))
    rows = store.list()
    assert {r.memory_id for r in rows} == {"a", "b"}


def test_list_con_kind(store) -> None:
    store.save(_rec(memory_id="a"))
    store.save(_rec(memory_id="b", kind="note"))
    rows = store.list(kind="decision")
    assert [r.memory_id for r in rows] == ["a"]


def test_list_limit_offset(store) -> None:
    for i in range(5):
        store.save(_rec(memory_id=f"m{i}", title=f"t{i}"))
    rows = store.list(limit=2, offset=2)
    assert len(rows) == 2


def test_list_error(store, tmp_path) -> None:
    bad = SQLiteMemoryStore(tmp_path / "no.db")
    assert bad.list() == []


def test_delete(store) -> None:
    store.save(_rec())
    assert store.delete("m1") is True
    assert store.get("m1") is None


def test_delete_error(store, tmp_path) -> None:
    bad = SQLiteMemoryStore(tmp_path / "no.db")
    assert bad.delete("x") is False


def test_search_fts5(store) -> None:
    store.save(_rec(memory_id="a", title="sqlite db", content="motor"))
    store.save(_rec(memory_id="b", kind="note", title="otra", content="sqlite rule"))
    rows = store.search("sqlite")
    assert len(rows) == 2
    rows_kind = store.search("sqlite", kind="note")
    assert [r.memory_id for r in rows_kind] == ["b"]


def test_search_vacio(store) -> None:
    assert store.search("") == []
    assert store.search("   ") == []


def test_search_fallback_like(store, tmp_path) -> None:
    path = tmp_path / "nolike.db"
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    no_fts = SQLiteMemoryStore(path)
    no_fts.save(_rec(memory_id="a", content="patron unico abc"))
    conn = sqlite3.connect(path)
    conn.execute("DROP TABLE op_memory_fts")
    conn.commit()
    conn.close()
    rows = no_fts.search("abc")
    assert [r.memory_id for r in rows] == ["a"]
    rows_kind = no_fts.search("abc", kind="decision")
    assert [r.memory_id for r in rows_kind] == ["a"]


def test_link_asset(store) -> None:
    store.save(_rec())
    assert store.link_asset("m1", "a2") is True
    got = store.get("m1")
    assert got.related_assets == ("a1", "a2")


def test_link_asset_ya_existe(store) -> None:
    store.save(_rec())
    assert store.link_asset("m1", "a1") is True
    assert store.get("m1").related_assets == ("a1",)


def test_link_asset_no_existe(store) -> None:
    assert store.link_asset("nada", "a1") is False


def test_link_asset_error(store, db_path) -> None:
    conn = sqlite3.connect(db_path)
    conn.executescript(
        "CREATE TRIGGER fail_link BEFORE UPDATE ON op_memory BEGIN"
        " SELECT RAISE(ABORT, 'boom');"
        " END;"
    )
    conn.commit()
    conn.close()
    store.save(_rec())
    assert store.link_asset("m1", "a2") is False


def test_row_to_record_campos_nulos(db_path, store) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO op_memory (memory_id, kind, title, content) "
        "VALUES ('n', 'note', 't', 'c')"
    )
    conn.commit()
    conn.close()
    r = store.get("n")
    assert r is not None
    assert r.related_assets == ()
    assert r.created_at == ""


def test_count(store) -> None:
    assert store.count() == 0
    store.save(_rec(memory_id="a"))
    store.save(_rec(memory_id="b", kind="note"))
    assert store.count() == 2
    assert store.count(kind="note") == 1


def test_count_error(store, tmp_path) -> None:
    bad = SQLiteMemoryStore(tmp_path / "no.db")
    assert bad.count() == 0


def test_row_to_record_json_invalido(db_path, store) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO op_memory (memory_id, kind, title, content, related_assets, tags, metadata) "
        "VALUES ('r', 'note', 't', 'c', 'no-json', 'no-json', 'no-json')"
    )
    conn.commit()
    conn.close()
    r = store.get("r")
    assert r is not None
    assert r.related_assets == ()
    assert r.tags == ()
    assert r.metadata == {}

"""Tests de integración para HybridMemory.

Requiere: motor.intelligence.memory.hybrid.HybridMemory
SQLite en memoria (no requiere Qdrant ni disco).
"""

from __future__ import annotations

import sqlite3
import types
from datetime import UTC, datetime
from typing import Any

import pytest

from motor.intelligence.memory.hybrid import HybridMemory
from motor.intelligence.memory.record import MemoryType


def test_store_and_search():
    mem = HybridMemory(db_path=":memory:")

    rid = mem.store(payload="El cielo es azul", metadata={"source": "test"}, memory_type=MemoryType.SEMANTIC)
    assert rid
    assert len(rid) == 32  # uuid4 hex

    results = mem.search("cielo", k=5)
    assert len(results) == 1
    assert results[0].payload == "El cielo es azul"


def test_search_no_results():
    mem = HybridMemory(db_path=":memory:")
    mem.store(payload="test")
    results = mem.search("xyz_nonexistent", k=5)
    assert len(results) == 0


def test_search_with_type_filter():
    mem = HybridMemory(db_path=":memory:")
    mem.store(payload="working memory", memory_type=MemoryType.WORKING)
    mem.store(payload="semantic memory", memory_type=MemoryType.SEMANTIC)

    working = mem.search("memory", k=10, memory_type=MemoryType.WORKING)
    assert len(working) == 1
    assert working[0].payload == "working memory"

    semantic = mem.search("memory", k=10, memory_type=MemoryType.SEMANTIC)
    assert len(semantic) == 1
    assert semantic[0].payload == "semantic memory"


def test_get_by_id():
    mem = HybridMemory(db_path=":memory:")
    rid = mem.store(payload="get me")
    recovered = mem.get(rid)
    assert recovered is not None
    assert recovered.payload == "get me"


def test_get_nonexistent():
    mem = HybridMemory(db_path=":memory:")
    assert mem.get("nonexistent") is None


def test_delete():
    mem = HybridMemory(db_path=":memory:")
    rid = mem.store(payload="to delete")
    assert mem.count() == 1
    assert mem.delete(rid)
    assert mem.count() == 0


def test_count():
    mem = HybridMemory(db_path=":memory:")
    assert mem.count() == 0
    mem.store(payload="a")
    mem.store(payload="b")
    mem.store(payload="c")
    assert mem.count() == 3


def test_count_by_type():
    mem = HybridMemory(db_path=":memory:")
    mem.store(payload="a", memory_type=MemoryType.WORKING)
    mem.store(payload="b", memory_type=MemoryType.SEMANTIC)
    assert mem.count(MemoryType.WORKING) == 1
    assert mem.count(MemoryType.SEMANTIC) == 1


def test_health():
    mem = HybridMemory(db_path=":memory:")
    h = mem.health()
    assert "total_records" in h
    assert "vector_store_ok" in h
    assert h["total_records"] == 0


def test_multiple_stores():
    mem = HybridMemory(db_path=":memory:")
    ids = [mem.store(payload=f"record {i}") for i in range(10)]
    assert len(set(ids)) == 10  # all unique

    results = mem.search("record", k=10)
    assert len(results) == 10


def test_search_ranking():
    mem = HybridMemory(db_path=":memory:")
    mem.store(payload="python programming language for web development")
    mem.store(payload="java is also used for web applications")
    mem.store(payload="snakes are reptiles not programming")

    # FTS5 ranks by BM25 — python should rank higher for "python"
    results = mem.search("python", k=5)
    assert len(results) >= 1
    assert "python" in results[0].payload.lower()


# ── ramas de error / edge ───────────────────────────────────────────────────


def _fake_conn(**overrides: Any) -> types.SimpleNamespace:
    defaults: dict[str, Any] = {
        "execute": lambda *a, **k: None,
        "commit": lambda: None,
        "close": lambda: None,
        "executescript": lambda *a, **k: None,
    }
    defaults.update(overrides)
    return types.SimpleNamespace(**defaults)


def _boom(*a: Any, **k: Any) -> Any:
    raise sqlite3.Error("boom")


def test_context_manager_close_repetido():
    with HybridMemory(db_path=":memory:") as mem:
        mem.store(payload="ctx")
        assert mem.count() == 1
    mem.close()  # segundo close es no-op


def test_close_exception_logueada():
    mem = HybridMemory(db_path=":memory:")
    mem._get_conn()

    class FailingConn:
        def close(self) -> None:
            raise RuntimeError("close fail")

        def execute(self, *a: Any, **k: Any) -> None:
            return None  # pragma: no cover

        def commit(self) -> None:
            return None  # pragma: no cover

    mem._conn = FailingConn()  # type: ignore[assignment]
    mem.close()
    assert mem._conn is None


def test_clear_error_logueado():
    mem = HybridMemory(db_path=":memory:")
    mem._get_conn()
    mem._conn = _fake_conn(execute=_boom)  # type: ignore[assignment]
    mem.clear()


def test_clear_ok():
    mem = HybridMemory(db_path=":memory:")
    mem.store(payload="a")
    mem.store(payload="b")
    assert mem.count() == 2
    mem.clear()
    assert mem.count() == 0


def test_store_error_relanza():
    mem = HybridMemory(db_path=":memory:")
    mem._get_conn()
    mem._conn = _fake_conn(execute=_boom)  # type: ignore[assignment]
    with pytest.raises(sqlite3.Error):
        mem.store(payload="fail")


class _FakeVectorStore:
    def __init__(self, fail: bool = False) -> None:
        self._fail = fail

    def guardar_incidente(self, incident: dict) -> Any:
        if self._fail:
            raise RuntimeError("vector down")
        return None

    def buscar_similares(self, vector: list[float], limite: int = 5) -> Any:
        if self._fail:
            raise RuntimeError("vector down")
        return []


def test_vector_store_ok():
    vs = _FakeVectorStore(fail=False)
    mem = HybridMemory(vector_store=vs, db_path=":memory:")
    rid = mem.store(payload="vect", vector=[0.1, 0.2])
    assert rid
    assert mem.health()["vector_store_ok"] is True


def test_vector_store_fail_degrada():
    vs = _FakeVectorStore(fail=True)
    mem = HybridMemory(vector_store=vs, db_path=":memory:")
    rid = mem.store(payload="vect", vector=[0.1, 0.2])  # no lanza
    assert rid
    assert mem.health()["vector_store_ok"] is False


def test_search_query_vacia():
    mem = HybridMemory(db_path=":memory:")
    mem.store(payload="x")
    assert mem.search("") == []
    assert mem.search("   ") == []


def test_search_fts_error_degradado():
    mem = HybridMemory(db_path=":memory:")
    mem._get_conn()

    def fts_boom(query: str, *args: Any) -> Any:
        if "MATCH" in query.upper():
            raise sqlite3.OperationalError("fts syntax error")
        return None

    mem._conn = _fake_conn(execute=fts_boom)  # type: ignore[assignment]
    assert mem.search("bad query") == []


def test_search_aplica_defaults_filas_invalidas():
    mem = HybridMemory(db_path=":memory:")
    conn = mem._get_conn()
    ts = datetime.now(UTC).isoformat()
    conn.execute(
        "INSERT INTO memory_metadata (id, memory_type, created_at, metadata) VALUES (?,?,?,?)",
        ("r1", "BOGUS", ts, "no-json"),
    )
    conn.execute("INSERT INTO memory_fts (id, text, metadata) VALUES (?,?,?)", ("r1", "foo", "no-json"))
    conn.commit()

    results = mem.search("foo")
    assert len(results) == 1
    assert results[0].type == MemoryType.WORKING
    assert "no-json" not in results[0].metadata
    assert results[0].metadata.get("access_count") == 0


def test_get_excepcion_devuelve_none():
    mem = HybridMemory(db_path=":memory:")
    mem._get_conn()
    mem._conn = _fake_conn(execute=_boom)  # type: ignore[assignment]
    assert mem.get("cualquier") is None


def test_get_aplica_defaults_filas_invalidas():
    mem = HybridMemory(db_path=":memory:")
    conn = mem._get_conn()
    conn.execute(
        "INSERT INTO memory_metadata (id, memory_type, created_at, metadata) VALUES (?,?,?,?)",
        ("g1", "RARO", datetime.now(UTC).isoformat(), "[1,2"),
    )
    conn.commit()
    rec = mem.get("g1")
    assert rec is not None
    assert rec.type == MemoryType.WORKING
    assert "no-json" not in rec.metadata
    assert rec.metadata.get("access_count") == 0


def test_delete_error_devuelve_false():
    mem = HybridMemory(db_path=":memory:")
    mem._get_conn()
    mem._conn = _fake_conn(execute=_boom)  # type: ignore[assignment]
    assert mem.delete("x") is False


def test_count_error_devuelve_cero():
    mem = HybridMemory(db_path=":memory:")
    mem._get_conn()
    mem._conn = _fake_conn(execute=_boom)  # type: ignore[assignment]
    assert mem.count() == 0
    assert mem.count(MemoryType.WORKING) == 0


def test_health_count_error(monkeypatch: pytest.MonkeyPatch):
    mem = HybridMemory(db_path=":memory:")
    mem.store(payload="x")

    def boom(*a: Any, **k: Any) -> Any:
        raise sqlite3.Error("boom")

    monkeypatch.setattr(mem, "count", boom)
    h = mem.health()
    assert h["total_records"] == 0
    assert h["vector_store_ok"] is False

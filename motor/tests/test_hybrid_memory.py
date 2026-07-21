"""Tests de integración para HybridMemory.

Requiere: motor.intelligence.memory.hybrid.HybridMemory
SQLite en memoria (no requiere Qdrant ni disco).
"""

from __future__ import annotations

from motor.intelligence.memory.hybrid import HybridMemory
from motor.intelligence.memory.record import MemoryType


def test_store_and_search():
    mem = HybridMemory(db_path=":memory:")

    rid = mem.store(payload="El cielo es azul", metadata={"source": "test"}, memory_type=MemoryType.SEMANTIC)
    assert rid
    assert len(rid) == 16  # uuid4 hex

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

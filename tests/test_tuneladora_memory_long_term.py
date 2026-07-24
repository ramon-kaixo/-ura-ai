"""Tests for LongTermMemory (scripts/pro/tuneladora/memory/long_term.py)."""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.pro.tuneladora.memory.long_term import LongTermMemory, LTMEntry


@pytest.fixture
def ltm(tmp_path: Path) -> LongTermMemory:
    return LongTermMemory(tmp_path / "test_ltm.db")


class TestStoreRetrieve:
    def test_store_and_retrieve(self, ltm: LongTermMemory) -> None:
        entry = LTMEntry(key="test:1", value={"a": 1}, source="unit", tags=("tag1",))
        ltm.store(entry)
        retrieved = ltm.retrieve("test:1")
        assert retrieved is not None
        assert retrieved.value == {"a": 1}
        assert retrieved.source == "unit"
        assert "tag1" in retrieved.tags

    def test_retrieve_missing(self, ltm: LongTermMemory) -> None:
        assert ltm.retrieve("missing") is None

    def test_store_updates(self, ltm: LongTermMemory) -> None:
        ltm.store(LTMEntry(key="k", value={"v": 1}, source="src"))
        ltm.store(LTMEntry(key="k", value={"v": 2}, source="src"))
        retrieved = ltm.retrieve("k")
        assert retrieved is not None
        assert retrieved.value == {"v": 2}


class TestSearch:
    def test_search_by_source(self, ltm: LongTermMemory) -> None:
        ltm.store(LTMEntry(key="a", value={"x": 1}, source="src1"))
        ltm.store(LTMEntry(key="b", value={"y": 2}, source="src2"))
        results = ltm.search(source="src1")
        assert len(results) == 1
        assert results[0].key == "a"

    def test_search_by_tag(self, ltm: LongTermMemory) -> None:
        ltm.store(LTMEntry(key="a", value={}, source="s", tags=("critical",)))
        ltm.store(LTMEntry(key="b", value={}, source="s", tags=("info",)))
        results = ltm.search(tag="critical")
        assert len(results) == 1

    def test_search_limit(self, ltm: LongTermMemory) -> None:
        for i in range(10):
            ltm.store(LTMEntry(key=f"k{i}", value={"n": i}, source="s"))
        assert len(ltm.search(limit=3)) == 3


class TestDelete:
    def test_delete_existing(self, ltm: LongTermMemory) -> None:
        ltm.store(LTMEntry(key="k", value={}, source="s"))
        assert ltm.delete("k")
        assert ltm.retrieve("k") is None

    def test_delete_missing(self, ltm: LongTermMemory) -> None:
        assert not ltm.delete("missing")


class TestMisc:
    def test_count(self, ltm: LongTermMemory) -> None:
        ltm.store(LTMEntry(key="a", value={}, source="s"))
        ltm.store(LTMEntry(key="b", value={}, source="s"))
        assert ltm.count() == 2

    def test_vacuum(self, ltm: LongTermMemory) -> None:
        ltm.vacuum()

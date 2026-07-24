"""Tests for ShortTermMemory (scripts/pro/tuneladora/memory/short_term.py)."""
from __future__ import annotations

import time

import pytest

from scripts.pro.tuneladora.memory.short_term import ShortTermMemory


@pytest.fixture
def stm() -> ShortTermMemory:
    return ShortTermMemory(max_size=10, default_ttl=300.0)


class TestBasic:
    def test_set_and_get(self, stm: ShortTermMemory) -> None:
        stm.set("key", "value")
        assert stm.get("key") == "value"

    def test_get_missing(self, stm: ShortTermMemory) -> None:
        assert stm.get("missing") is None

    def test_has(self, stm: ShortTermMemory) -> None:
        stm.set("k", "v")
        assert stm.has("k")
        assert not stm.has("missing")

    def test_delete(self, stm: ShortTermMemory) -> None:
        stm.set("k", "v")
        stm.delete("k")
        assert not stm.has("k")

    def test_clear(self, stm: ShortTermMemory) -> None:
        stm.set("a", 1)
        stm.set("b", 2)
        stm.clear()
        assert stm.size() == 0


class TestTTL:
    def test_expired_returns_none(self, stm: ShortTermMemory) -> None:
        stm.set("k", "v", ttl=0.001)
        time.sleep(0.01)
        assert stm.get("k") is None

    def test_get_evicts_expired(self, stm: ShortTermMemory) -> None:
        stm.set("k1", "v1", ttl=0.001)
        stm.set("k2", "v2", ttl=300)
        time.sleep(0.01)
        stm.get("k1")
        assert not stm.has("k1")
        assert stm.has("k2")


class TestEviction:
    def test_max_size_evicts_lru(self, stm: ShortTermMemory) -> None:
        for i in range(12):
            stm.set(f"k{i}", i)
        assert stm.size() <= 10
        assert not stm.has("k0")

    def test_max_size_preserves_recent(self, stm: ShortTermMemory) -> None:
        for i in range(10):
            stm.set(f"k{i}", i)
        _ = stm.get("k0")
        stm.set("k10", 10)
        assert stm.has("k0")
        assert not stm.has("k1")

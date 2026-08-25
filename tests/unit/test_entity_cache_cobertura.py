"""Tests for motor/core/fusion/stages/entity_cache.py (LRUCache)."""
from __future__ import annotations

from motor.core.fusion.models import ResolvedEntity
from motor.core.fusion.stages.entity_cache import LRUCache


def _entity(eid: str) -> ResolvedEntity:
    return ResolvedEntity(entity_id=eid, canonical_name=eid, confidence=0.9)


class TestLRUCache:
    def test_put_get(self) -> None:
        c = LRUCache(maxsize=4)
        e = _entity("a")
        c.put("a", e)
        assert c.get("a") == e
        assert c.size == 1

    def test_get_missing(self) -> None:
        c = LRUCache()
        assert c.get("nope") is None

    def test_eviction_lru(self) -> None:
        c = LRUCache(maxsize=2)
        c.put("a", _entity("a"))
        c.put("b", _entity("b"))
        c.put("c", _entity("c"))
        assert c.get("a") is None  # a fue el LRU, expulsado
        assert c.get("b") is not None
        assert c.get("c") is not None
        assert c.size == 2

    def test_access_reorders(self) -> None:
        c = LRUCache(maxsize=2)
        c.put("a", _entity("a"))
        c.put("b", _entity("b"))
        c.get("a")  # a se vuelve MRU
        c.put("c", _entity("c"))  # b es ahora el LRU
        assert c.get("a") is not None
        assert c.get("b") is None

    def test_properties(self) -> None:
        c = LRUCache(maxsize=8)
        assert c.maxsize == 8
        assert c.size == 0

    def test_clear(self) -> None:
        c = LRUCache()
        c.put("a", _entity("a"))
        c.put("b", _entity("b"))
        c.clear()
        assert c.size == 0
        assert c.get("a") is None

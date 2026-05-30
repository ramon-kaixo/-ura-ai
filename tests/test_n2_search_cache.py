#!/usr/bin/env python3
"""Tests for core/ura_search_cache.py (N2 Fase 1)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from core.ura_search_cache import SearchCache, _fingerprint

pytestmark = pytest.mark.asyncio


async def _fresh_cache(tmp_path: Path) -> SearchCache:
    c = SearchCache(db_path=tmp_path / "test_cache.db")
    await c.initialize()
    return c


async def test_fingerprint_deterministic():
    assert _fingerprint("hola", "2024-01-01", "2024-01-31") == _fingerprint(
        "  HOLA  ", "2024-01-01", "2024-01-31"
    )
    assert _fingerprint("a") != _fingerprint("b")


async def test_put_and_get_returns_cached(tmp_path):
    cache = await _fresh_cache(tmp_path)
    results = [{"url": "https://example.com", "titulo": "Example"}]
    fp = await cache.put("query uno", results, maleta_id="m1", score_calidad=0.8)
    assert len(fp) == 64

    cached = await cache.get("query uno", maleta_id="m1")
    assert cached is not None
    assert cached["results"] == results
    assert cached["score_calidad"] == 0.8
    assert cached["hits"] == 1


async def test_get_miss_returns_none(tmp_path):
    cache = await _fresh_cache(tmp_path)
    assert await cache.get("nada") is None


async def test_expired_entries_not_returned(tmp_path):
    cache = await _fresh_cache(tmp_path)
    await cache.put("expira", [{"url": "u"}], ttl_hours=0)
    # With ttl_hours=0, expires_at == created_at → already expired
    assert await cache.get("expira") is None


async def test_cleanup_expired(tmp_path):
    cache = await _fresh_cache(tmp_path)
    await cache.put("a", [{"url": "u"}], ttl_hours=0)
    removed = await cache.cleanup_expired()
    assert removed >= 1


async def test_stats_reports_entries(tmp_path):
    cache = await _fresh_cache(tmp_path)
    await cache.put("x", [{"url": "u"}])
    stats = await cache.stats()
    assert stats["entries"] >= 1


async def test_concurrent_writes_are_safe(tmp_path):
    cache = await _fresh_cache(tmp_path)

    async def writer(i):
        await cache.put(f"q{i}", [{"url": f"https://u/{i}"}], maleta_id="m1")

    await asyncio.gather(*[writer(i) for i in range(20)])
    stats = await cache.stats()
    assert stats["entries"] == 20

"""Tests de query_cache."""

import asyncio

from core.query_cache import AsyncQueryCache


def test_cache_basic():
    cache = AsyncQueryCache(max_size=10, ttl=60)

    async def _run():
        key = cache.compute_key("test_query", use_reranker=False, use_hybrid=False, top_k=5)
        assert key is not None
        assert len(key) == 64  # SHA-256 hex

        # Miss
        cached = await cache.get(key)
        assert cached is None

        # Set + hit
        await cache.set(key, [{"test": "data"}])
        cached = await cache.get(key)
        assert cached is not None
        assert cached[0]["test"] == "data"

        # Clear
        await cache.clear()
        cached = await cache.get(key)
        assert cached is None

    asyncio.run(_run())


def test_cache_key_unique():
    cache = AsyncQueryCache()
    k1 = cache.compute_key("test")
    k2 = cache.compute_key("test")
    k3 = cache.compute_key("different")
    assert k1 == k2  # Determinista
    assert k1 != k3  # Diferente para diferentes queries


def test_cache_key_params():
    cache = AsyncQueryCache()
    k1 = cache.compute_key("test", use_reranker=True)
    k2 = cache.compute_key("test", use_reranker=False)
    assert k1 != k2  # Diferentes parámetros → diferentes keys

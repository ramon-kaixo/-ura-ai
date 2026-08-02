"""Tests para core/json_logger.py y core/query_cache.py."""
from __future__ import annotations

import logging
from unittest import mock

import pytest

from core.json_logger import StructuredLogger
from core.query_cache import AsyncQueryCache


class TestStructuredLogger:
    def test_deprecation_warning(self) -> None:
        with pytest.warns(DeprecationWarning, match="StructuredLogger is deprecated"):
            StructuredLogger("test_dep", level=logging.DEBUG)

    def test_niveles(self) -> None:
        with mock.patch("sys.stdout", mock.Mock()):
            logger = StructuredLogger("test_logger", level=logging.DEBUG)
            logger.info("msg info", key="v")
            logger.warning("msg warn")
            logger.error("msg error", a=1)
            logger.critical("msg crit")
            logger.debug("msg debug")

    def test_info_sin_extra(self) -> None:
        with mock.patch("sys.stdout", mock.Mock()):
            logger = StructuredLogger("test_logger2")
            logger.info("solo mensaje")

    def test_json_formatter_usado(self) -> None:
        with mock.patch("sys.stdout", mock.Mock()):
            logger = StructuredLogger("test_logger3")
            handler = logger._logger.handlers[0]
            assert handler.formatter is not None


class TestAsyncQueryCache:
    def test_compute_key_determinista(self) -> None:
        c = AsyncQueryCache()
        assert c.compute_key("  HOLA  ") == c.compute_key("hola")
        assert c.compute_key("a", use_reranker=True) != c.compute_key("a", use_reranker=False)

    @pytest.mark.asyncio
    async def test_get_set_roundtrip(self) -> None:
        c = AsyncQueryCache()
        key = c.compute_key("hola")
        await c.set(key, [{"r": 1}])
        assert await c.get(key) == [{"r": 1}]

    @pytest.mark.asyncio
    async def test_get_miss(self) -> None:
        c = AsyncQueryCache()
        assert await c.get("noexiste") is None

    @pytest.mark.asyncio
    async def test_ttl_expirado(self, monkeypatch) -> None:
        c = AsyncQueryCache(ttl=10)
        key = c.compute_key("hola")
        await c.set(key, [{"r": 1}])
        monkeypatch.setattr("core.query_cache.time.monotonic", lambda: 99999)
        assert await c.get(key) is None

    @pytest.mark.asyncio
    async def test_lru_eviction(self) -> None:
        c = AsyncQueryCache(max_size=2)
        for i in range(4):
            await c.set(f"k{i}", [{"i": i}])
        assert len(c.cache) == 2
        assert "k0" not in c.cache
        assert "k3" in c.cache

    @pytest.mark.asyncio
    async def test_clear(self) -> None:
        c = AsyncQueryCache()
        await c.set("k", [{"a": 1}])
        await c.clear()
        assert len(c.cache) == 0

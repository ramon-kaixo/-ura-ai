"""Tests para core/model_router/cache.py — PromptCache."""
from __future__ import annotations

from unittest import mock

import pytest

from core.model_router.cache import CACHE_TTL, PromptCache


@pytest.fixture(autouse=True)
def _reset_metrics(monkeypatch):
    monkeypatch.setattr("core.model_router.metrics.metrics.increment", mock.Mock())
    yield


@pytest.fixture
def cache() -> PromptCache:
    return PromptCache(ttl=100)


class TestPromptCache:
    def test_miss_inicial(self, cache: PromptCache) -> None:
        assert cache.get("hola", "chat") is None

    def test_set_get_roundtrip(self, cache: PromptCache) -> None:
        cache.set("hola", "chat", {"respuesta": "x"})
        assert cache.get("hola", "chat") == {"respuesta": "x"}

    def test_tipo_distinto_misma_palabra(self, cache: PromptCache) -> None:
        cache.set("hola", "chat", {"r": 1})
        assert cache.get("hola", "embedding") is None

    def test_hash_content_determinista(self, cache: PromptCache) -> None:
        assert cache._hash_content("abc") == cache._hash_content("abc")
        assert cache._hash_content("abc") != cache._hash_content("abd")

    def test_ttl_expirado(self, cache: PromptCache, monkeypatch) -> None:
        monkeypatch.setattr("core.model_router.cache.time.time", lambda: 100)
        cache.set("hola", "chat", {"r": 1})
        monkeypatch.setattr("core.model_router.cache.time.time", lambda: 200)
        assert cache.get("hola", "chat") is None  # ttl 100 ya paso

    def test_ttl_valido(self, cache: PromptCache, monkeypatch) -> None:
        cache.set("hola", "chat", {"r": 1})
        monkeypatch.setattr("core.model_router.cache.time.time", lambda: 50)
        assert cache.get("hola", "chat") == {"r": 1}

    def test_clear(self, cache: PromptCache) -> None:
        cache.set("a", "chat", {"r": 1})
        cache.clear()
        assert cache.get("a", "chat") is None

    def test_metrics_hit(self, cache: PromptCache) -> None:
        from core.model_router.cache import metrics

        cache.set("hola", "chat", {"r": 1})
        cache.get("hola", "chat")
        metrics.increment.assert_called_once_with("prompt_cache_hit", {"tipo": "chat"})

    def test_metrics_miss(self, cache: PromptCache) -> None:
        from core.model_router.cache import metrics

        cache.get("nada", "chat")
        metrics.increment.assert_called_once_with("prompt_cache_miss", {"tipo": "chat"})

    def test_singleton(self) -> None:
        from core.model_router.cache import prompt_cache

        assert isinstance(prompt_cache, PromptCache)
        assert prompt_cache.ttl == CACHE_TTL

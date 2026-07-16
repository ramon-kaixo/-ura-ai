"""Tests for vector_ollama.py — OllamaEmbedder."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from knowledge.engine.vector_ollama import OllamaEmbedder

if TYPE_CHECKING:
    from knowledge.engine.vector_base import Embedder


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_llm():
    """Fixture que parchea motor.core.llm.embed y health."""
    with (
        patch("knowledge.engine.vector_ollama._embed") as m_embed,
        patch("knowledge.engine.vector_ollama._health") as m_health,
    ):
        m_health.return_value = {"status": "ok", "modelos_disponibles": [], "latency_ms": 5}
        m_embed.return_value = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        yield {"embed": m_embed, "health": m_health}


# ── Tests ───────────────────────────────────────────────────────────────────


class TestOllamaEmbedderProtocol:
    """Verifica que OllamaEmbedder puede tratarse como Embedder."""

    def test_is_embedder(self, mock_llm):
        embedder: Embedder = OllamaEmbedder(model="test-model")
        assert isinstance(embedder, OllamaEmbedder)


class TestEmbed:
    """Tests para embed()."""

    def test_embed_texts(self, mock_llm):
        mock_llm["embed"].return_value = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        embedder = OllamaEmbedder(model="test-model")
        vectors = embedder.embed(["hello", "world"])
        assert len(vectors) == 2
        assert vectors[0] == [0.1, 0.2, 0.3]
        assert embedder.vector_size == 3
        mock_llm["embed"].assert_called_with(["hello", "world"], model="test-model")

    def test_embed_empty(self, mock_llm):
        embedder = OllamaEmbedder(model="test-model")
        assert embedder.embed([]) == []

    def test_embed_not_available(self, mock_llm):
        embedder = OllamaEmbedder(model="test-model")
        embedder._degraded = True
        assert embedder.embed(["text"]) == []

    def test_embed_cache_hit(self, mock_llm):
        mock_llm["embed"].return_value = [[0.1, 0.2]]
        embedder = OllamaEmbedder(model="test-model")
        v1 = embedder.embed(["hello"])
        v2 = embedder.embed(["hello"])
        assert v1 == v2
        assert mock_llm["embed"].call_count == 1

    def test_embed_no_cache_for_batch(self, mock_llm):
        mock_llm["embed"].return_value = [[0.1], [0.2], [0.3]]
        embedder = OllamaEmbedder(model="test-model")
        embedder.embed(["a", "b", "c"])
        mock_llm["embed"].return_value = [[0.4], [0.5], [0.6]]
        embedder.embed(["a", "b", "c"])
        assert mock_llm["embed"].call_count == 2

    def test_embed_cache_expiry(self, mock_llm):
        mock_llm["embed"].return_value = [[0.1, 0.2]]
        embedder = OllamaEmbedder(model="test-model", cache_ttl=1)
        embedder.embed(["hello"])
        time.sleep(1.1)
        v2 = embedder.embed(["hello"])
        assert mock_llm["embed"].call_count == 2
        assert v2 == [[0.1, 0.2]]

    def test_embed_http_error_degraded(self, mock_llm):
        mock_llm["embed"].side_effect = Exception("Ollama down")
        embedder = OllamaEmbedder(model="test-model")
        result = embedder.embed(["hello"])
        assert result == []
        assert embedder.available is False

    def test_embed_auto_detect_vector_size(self, mock_llm):
        mock_llm["embed"].return_value = [[0.1] * 768]
        embedder = OllamaEmbedder(model="test-model")
        embedder.embed(["hello"])
        assert embedder.vector_size == 768


class TestEmbedQuery:
    """Tests para embed_query()."""

    def test_embed_query(self, mock_llm):
        mock_llm["embed"].return_value = [[0.1, 0.2, 0.3]]
        embedder = OllamaEmbedder(model="test-model")
        vec = embedder.embed_query("test query")
        assert vec == [0.1, 0.2, 0.3]

    def test_embed_query_empty(self, mock_llm):
        embedder = OllamaEmbedder(model="test-model")
        assert embedder.embed_query("") == []

    def test_embed_query_not_available(self, mock_llm):
        embedder = OllamaEmbedder(model="test-model")
        embedder._degraded = True
        assert embedder.embed_query("test") == []


class TestProperties:
    """Tests para properties del protocolo."""

    def test_vector_size_default(self, mock_llm):
        embedder = OllamaEmbedder(model="test-model")
        assert embedder.vector_size == 0

    def test_max_input_tokens(self, mock_llm):
        embedder = OllamaEmbedder(model="test-model")
        assert embedder.max_input_tokens == 0

    def test_max_input_tokens_unknown(self, mock_llm):
        embedder = OllamaEmbedder(model="test-model")
        assert embedder.max_input_tokens == 0

    def test_available_true(self, mock_llm):
        mock_llm["health"].return_value = {"status": "ok", "modelos_disponibles": [], "latency_ms": 5}
        embedder = OllamaEmbedder(model="test-model")
        assert embedder.available is True

    def test_available_false(self, mock_llm):
        embedder = OllamaEmbedder(model="test-model")
        embedder._degraded = True
        assert embedder.available is False

    def test_available_http_error(self, mock_llm):
        mock_llm["health"].return_value = {"status": "error", "detail": "Connection refused", "latency_ms": 100}
        embedder = OllamaEmbedder(model="test-model")
        embedder._degraded = True
        assert embedder.available is False
        assert not embedder.check_available()

    def test_available_after_degraded(self, mock_llm):
        mock_llm["embed"].side_effect = Exception("Ollama down")
        embedder = OllamaEmbedder(model="test-model")
        embedder.embed(["text"])
        assert embedder.available is False


class TestLifecycle:
    """Tests para close() y limpieza."""

    def test_close(self, mock_llm):
        embedder = OllamaEmbedder(model="test-model")
        embedder.close()


class TestDeterminism:
    """Verifica determinismo (depende del modelo, mock simula)."""

    def test_determinism_embed(self, mock_llm):
        mock_llm["embed"].return_value = [[0.1, 0.2, 0.3]]
        e1 = OllamaEmbedder(model="test-model")
        e2 = OllamaEmbedder(model="test-model")
        v1 = e1.embed(["hello"])
        v2 = e2.embed(["hello"])
        assert v1 == v2

    def test_determinism_embed_query(self, mock_llm):
        mock_llm["embed"].return_value = [[0.1, 0.2, 0.3]]
        e1 = OllamaEmbedder(model="test-model")
        e2 = OllamaEmbedder(model="test-model")
        assert e1.embed_query("hello") == e2.embed_query("hello")

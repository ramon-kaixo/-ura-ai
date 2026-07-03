"""Tests for vector_ollama.py — OllamaEmbedder."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import httpx
import pytest

from knowledge.engine.vector_ollama import OllamaEmbedder

if TYPE_CHECKING:
    from knowledge.engine.vector_base import Embedder


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_client():
    """Fixture que parchea httpx.Client y retorna el mock para inspección."""
    with patch("knowledge.engine.vector_ollama.httpx.Client") as m:
        instance = MagicMock()
        m.return_value = instance
        yield instance


def _make_embed_response(embeddings: list[list[float]]) -> MagicMock:
    """Crea una respuesta mock para /api/embed."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"embeddings": embeddings}
    return resp


def _make_tags_response(*, ok: bool = True) -> MagicMock:
    """Crea una respuesta mock para /api/tags."""
    resp = MagicMock()
    resp.status_code = 200 if ok else 503
    return resp


def _make_show_response(num_ctx: int | None = 2048) -> MagicMock:
    """Crea una respuesta mock para /api/show (model info)."""
    resp = MagicMock()
    resp.status_code = 200
    modelfile = f"PARAMETER num_ctx {num_ctx}\n" if num_ctx else ""
    resp.json.return_value = {"modelfile": modelfile}
    return resp


# ── Tests ───────────────────────────────────────────────────────────────────


class TestOllamaEmbedderProtocol:
    """Verifica que OllamaEmbedder puede tratarse como Embedder."""

    def test_is_embedder(self, mock_client):
        mock_client.get.return_value = _make_tags_response(ok=True)
        embedder: Embedder = OllamaEmbedder(model="test-model")
        assert isinstance(embedder, OllamaEmbedder)


class TestEmbed:
    """Tests para embed()."""

    def test_embed_texts(self, mock_client):
        mock_client.get.return_value = _make_tags_response(ok=True)
        mock_client.post.return_value = _make_embed_response(
            [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]],
        )
        embedder = OllamaEmbedder(model="test-model")
        vectors = embedder.embed(["hello", "world"])
        assert len(vectors) == 2
        assert vectors[0] == [0.1, 0.2, 0.3]
        assert embedder.vector_size == 3
        mock_client.post.assert_called_with(
            "/api/embed",
            json={"model": "test-model", "input": ["hello", "world"]},
        )

    def test_embed_empty(self, mock_client):
        mock_client.get.return_value = _make_tags_response(ok=True)
        embedder = OllamaEmbedder(model="test-model")
        assert embedder.embed([]) == []

    def test_embed_not_available(self, mock_client):
        embedder = OllamaEmbedder(model="test-model")
        embedder._degraded = True
        assert embedder.embed(["text"]) == []

    def test_embed_cache_hit(self, mock_client):
        mock_client.get.return_value = _make_tags_response(ok=True)
        mock_client.post.return_value = _make_embed_response([[0.1, 0.2]])
        embedder = OllamaEmbedder(model="test-model")
        v1 = embedder.embed(["hello"])
        v2 = embedder.embed(["hello"])
        assert v1 == v2
        # Solo 1 llamada a POST (la segunda es cache)
        assert mock_client.post.call_count == 1

    def test_embed_no_cache_for_batch(self, mock_client):
        mock_client.get.return_value = _make_tags_response(ok=True)
        embedder = OllamaEmbedder(model="test-model")
        mock_client.post.return_value = _make_embed_response(
            [[0.1], [0.2], [0.3]],
        )
        embedder.embed(["a", "b", "c"])
        mock_client.post.return_value = _make_embed_response(
            [[0.4], [0.5], [0.6]],
        )
        embedder.embed(["a", "b", "c"])
        # Batch > 1 should NOT cache — each call goes to API
        assert mock_client.post.call_count == 2

    def test_embed_cache_expiry(self, mock_client):
        mock_client.get.return_value = _make_tags_response(ok=True)
        mock_client.post.return_value = _make_embed_response([[0.1, 0.2]])
        embedder = OllamaEmbedder(model="test-model", cache_ttl=1)
        embedder.embed(["hello"])
        time.sleep(1.1)
        v2 = embedder.embed(["hello"])
        # After TTL, should call API again
        assert mock_client.post.call_count == 2
        assert v2 == [[0.1, 0.2]]

    def test_embed_http_error_degraded(self, mock_client):
        mock_client.get.return_value = _make_tags_response(ok=True)
        mock_client.post.side_effect = httpx.HTTPError("Ollama down")
        embedder = OllamaEmbedder(model="test-model")
        result = embedder.embed(["hello"])
        assert result == []
        assert embedder.available is False  # degraded → not available

    def test_embed_auto_detect_vector_size(self, mock_client):
        mock_client.get.return_value = _make_tags_response(ok=True)
        mock_client.post.return_value = _make_embed_response(
            [[0.1] * 768],
        )
        embedder = OllamaEmbedder(model="test-model")
        embedder.embed(["hello"])
        assert embedder.vector_size == 768


class TestEmbedQuery:
    """Tests para embed_query()."""

    def test_embed_query(self, mock_client):
        mock_client.get.return_value = _make_tags_response(ok=True)
        mock_client.post.return_value = _make_embed_response([[0.1, 0.2, 0.3]])
        embedder = OllamaEmbedder(model="test-model")
        vec = embedder.embed_query("test query")
        assert vec == [0.1, 0.2, 0.3]

    def test_embed_query_empty(self, mock_client):
        mock_client.get.return_value = _make_tags_response(ok=True)
        embedder = OllamaEmbedder(model="test-model")
        assert embedder.embed_query("") == []

    def test_embed_query_not_available(self, mock_client):
        embedder = OllamaEmbedder(model="test-model")
        embedder._degraded = True
        assert embedder.embed_query("test") == []


class TestProperties:
    """Tests para properties del protocolo."""

    def test_vector_size_default(self, mock_client):
        mock_client.get.return_value = _make_tags_response(ok=True)
        embedder = OllamaEmbedder(model="test-model")
        assert embedder.vector_size == 0  # aún no detectado

    def test_max_input_tokens(self, mock_client):
        mock_client.get.return_value = _make_tags_response(ok=True)
        embedder = OllamaEmbedder(model="test-model")
        mock_client.post.return_value = _make_show_response(num_ctx=2048)
        assert embedder.max_input_tokens == 2048
        mock_client.post.assert_any_call(
            "/api/show",
            json={"model": "test-model"},
        )

    def test_max_input_tokens_unknown(self, mock_client):
        mock_client.get.return_value = _make_tags_response(ok=True)
        # /api/show fails
        mock_client.post.side_effect = httpx.HTTPError("not found")
        embedder = OllamaEmbedder(model="test-model")
        # Should survive error and return 0
        assert embedder.max_input_tokens == 0

    def test_available_true(self, mock_client):
        mock_client.get.return_value = _make_tags_response(ok=True)
        embedder = OllamaEmbedder(model="test-model")
        assert embedder.available is True

    def test_available_false(self, mock_client):
        embedder = OllamaEmbedder(model="test-model")
        embedder._degraded = True
        assert embedder.available is False

    def test_available_http_error(self, mock_client):
        mock_client.get.side_effect = httpx.HTTPError("Connection refused")
        embedder = OllamaEmbedder(model="test-model")
        embedder._degraded = True
        assert embedder.available is False
        # check_available does real HTTP check with backoff
        assert not embedder.check_available()

    def test_available_after_degraded(self, mock_client):
        mock_client.get.return_value = _make_tags_response(ok=True)
        mock_client.post.side_effect = httpx.HTTPError("Ollama down")
        embedder = OllamaEmbedder(model="test-model")
        embedder.embed(["text"])  # triggers degraded
        assert embedder.available is False  # degraded → not available


class TestLifecycle:
    """Tests para close() y limpieza."""

    def test_close(self, mock_client):
        mock_client.get.return_value = _make_tags_response(ok=True)
        embedder = OllamaEmbedder(model="test-model")
        embedder.close()
        mock_client.close.assert_called_once()


class TestDeterminism:
    """Verifica determinismo (depende del modelo, mock simula)."""

    def test_determinism_embed(self, mock_client):
        mock_client.get.return_value = _make_tags_response(ok=True)
        mock_client.post.return_value = _make_embed_response(
            [[0.1, 0.2, 0.3]],
        )
        e1 = OllamaEmbedder(model="test-model")
        e2 = OllamaEmbedder(model="test-model")
        v1 = e1.embed(["hello"])
        v2 = e2.embed(["hello"])
        assert v1 == v2

    def test_determinism_embed_query(self, mock_client):
        mock_client.get.return_value = _make_tags_response(ok=True)
        mock_client.post.return_value = _make_embed_response(
            [[0.1, 0.2, 0.3]],
        )
        e1 = OllamaEmbedder(model="test-model")
        e2 = OllamaEmbedder(model="test-model")
        assert e1.embed_query("hello") == e2.embed_query("hello")

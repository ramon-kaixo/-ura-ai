"""Tests para motor.core.llm.gemini (GeminiProvider).

La conftest autouse expulsa el módulo de sys.modules
se importa fresco
en el fixture para poder parchear get_secret y httpx.
"""
from __future__ import annotations

import asyncio
from unittest import mock

import httpx
import pytest

from motor.core.llm.base import FALLBACK_EMBEDDING_DIMENSION


@pytest.fixture()
def gemini_mod():
    import motor.core.llm.gemini

    return motor.core.llm.gemini


@pytest.fixture()
def provider(gemini_mod):
    secrets = {
        "GEMINI_API_KEY": "secret-val",
        "GEMINI_MODEL": "mi-modelo",
        "GEMINI_EMBEDDING_MODEL": "mi-embed",
        "GEMINI_TIMEOUT": "60",
        "GEMINI_TEMPERATURE": "0.9",
        "GEMINI_MAX_TOKENS": "512",
    }

    def _get(name: str, default: str | None = None):
        return secrets.get(name, default)

    with mock.patch.object(gemini_mod, "get_secret", side_effect=_get):
        return gemini_mod.GeminiProvider()


class TestInit:
    def test_capabilities(self, provider) -> None:
        caps = provider.capabilities
        assert caps["chat"] is True
        assert caps["embeddings"] is True
        assert caps["streaming"] is True
        assert caps["tools"] is True
        assert caps["multimodal"] is True
        assert caps["vision"] is True
        assert caps["max_context"] == 1048576
        assert caps["max_output"] == 8192

    def test_defaults(self, gemini_mod) -> None:
        with mock.patch.object(gemini_mod, "get_secret", side_effect=lambda name, default=None: default):
            p = gemini_mod.GeminiProvider()
        assert p._model == "gemini-2.0-flash-001"
        assert p._embedding_model == "text-embedding-004"
        assert p._timeout == 120
        assert p._temperature == 0.3
        assert p._max_tokens == 1024

    def test_custom_values(self, gemini_mod) -> None:
        secrets = {
            "GEMINI_API_KEY": "k",
            "GEMINI_MODEL": "mi-modelo",
            "GEMINI_EMBEDDING_MODEL": "mi-embed",
            "GEMINI_TIMEOUT": "60",
            "GEMINI_TEMPERATURE": "0.9",
            "GEMINI_MAX_TOKENS": "512",
        }

        def _get(name: str, default: str | None = None):
            return secrets.get(name, default)

        with mock.patch.object(gemini_mod, "get_secret", side_effect=_get):
            p = gemini_mod.GeminiProvider()
        assert p._model == "mi-modelo"
        assert p._embedding_model == "mi-embed"
        assert p._timeout == 60
        assert p._temperature == 0.9
        assert p._max_tokens == 512

    def test_headers(self, provider) -> None:
        headers = provider._headers()
        assert headers["x-goog-api-key"] == "secret-val"
        assert headers["Content-Type"] == "application/json"

    def test_base_url(self, provider) -> None:
        assert provider._base_url("gemini-x") == (
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-x"
        )


class TestGenerate:
    def _response(self, parts: list[str] | None = None, usage: dict | None = None) -> mock.Mock:
        r = mock.Mock()
        r.status_code = 200
        r.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": p} for p in (parts or [])]}}],
            "usageMetadata": usage or {"promptTokenCount": 5, "candidatesTokenCount": 3},
        }
        return r

    def test_success_concatenates_parts(self, provider, gemini_mod) -> None:
        with mock.patch.object(gemini_mod.httpx, "post", return_value=self._response(["hola", " mundo"])) as post:
            result = provider.generate("prompt")
        assert result == "hola mundo"
        assert post.call_args[0][0].endswith(":generateContent")
        payload = post.call_args.kwargs["json"]
        assert payload["contents"] == [{"parts": [{"text": "prompt"}]}]
        assert payload["generationConfig"]["temperature"] == 0.9
        assert payload["generationConfig"]["maxOutputTokens"] == 512
        assert post.call_args.kwargs["headers"]["x-goog-api-key"] == "secret-val"

    def test_no_candidates(self, provider, gemini_mod) -> None:
        r = mock.Mock()
        r.status_code = 200
        r.json.return_value = {"candidates": []}
        with mock.patch.object(gemini_mod.httpx, "post", return_value=r):
            result = provider.generate("p")
        assert result == "El modelo no generó ninguna respuesta."

    def test_empty_parts(self, provider, gemini_mod) -> None:
        with mock.patch.object(gemini_mod.httpx, "post", return_value=self._response([])):
            result = provider.generate("p")
        assert result == "El modelo no generó ninguna respuesta."

    def test_custom_model(self, provider, gemini_mod) -> None:
        with mock.patch.object(gemini_mod.httpx, "post", return_value=self._response(["x"])) as post:
            provider.generate("p", model="custom-model")
        assert post.call_args[0][0] == (
            "https://generativelanguage.googleapis.com/v1beta/models/custom-model:generateContent"
        )

    def test_timeout(self, provider, gemini_mod) -> None:
        with mock.patch.object(gemini_mod.httpx, "post", side_effect=httpx.TimeoutException("t")):
            result = provider.generate("p")
        assert "tiempo de espera" in result

    def test_http_error(self, provider, gemini_mod) -> None:
        error = httpx.HTTPStatusError("bad", request=mock.Mock(), response=mock.Mock(status_code=429))
        with mock.patch.object(gemini_mod.httpx, "post", side_effect=error):
            result = provider.generate("p")
        assert "429" in result

    def test_request_error(self, provider, gemini_mod) -> None:
        with mock.patch.object(gemini_mod.httpx, "post", side_effect=httpx.RequestError("conn")):
            result = provider.generate("p")
        assert "No se pudo conectar" in result

    def test_unexpected_error(self, provider, gemini_mod) -> None:
        with mock.patch.object(gemini_mod.httpx, "post", side_effect=RuntimeError("boom")):
            result = provider.generate("p")
        assert "Error interno" in result


class TestEmbed:
    def _batch_response(self) -> mock.Mock:
        r = mock.Mock()
        r.status_code = 200
        r.json.return_value = {"embeddings": [{"values": [0.1]}, {"values": [0.2]}]}
        return r

    def test_batch_success(self, provider, gemini_mod) -> None:
        with mock.patch.object(gemini_mod.httpx, "post", return_value=self._batch_response()) as post:
            result = provider.embed(["a", "b"])
        assert result == [[0.1], [0.2]]
        assert post.call_args[0][0].endswith(":batchEmbedContents")
        payload = post.call_args.kwargs["json"]
        assert len(payload["requests"]) == 2
        assert payload["requests"][0]["content"]["parts"] == [{"text": "a"}]

    def test_custom_model(self, provider, gemini_mod) -> None:
        with mock.patch.object(gemini_mod.httpx, "post", return_value=self._batch_response()) as post:
            provider.embed(["a"], model="embed-2")
        payload = post.call_args.kwargs["json"]
        assert payload["requests"][0]["model"] == "models/embed-2"

    def test_error_zero_fallback(self, provider, gemini_mod) -> None:
        with mock.patch.object(gemini_mod.httpx, "post", side_effect=httpx.RequestError("conn")):
            result = provider.embed(["a", "b"])
        assert result == [[0.0] * FALLBACK_EMBEDDING_DIMENSION, [0.0] * FALLBACK_EMBEDDING_DIMENSION]


class TestEmbedAsync:
    def test_batch_success(self, provider, gemini_mod) -> None:
        r = mock.Mock()
        r.status_code = 200
        r.json.return_value = {"embeddings": [{"values": [0.1]}]}
        with mock.patch.object(gemini_mod.httpx, "post", return_value=r):
            result = asyncio.run(provider.embed_async(["a"]))
        assert result == [[0.1]]

    def test_error_zero_fallback(self, provider, gemini_mod) -> None:
        with mock.patch.object(gemini_mod.httpx, "post", side_effect=httpx.RequestError("conn")):
            result = asyncio.run(provider.embed_async(["a"]))
        assert result == [[0.0] * FALLBACK_EMBEDDING_DIMENSION]


class TestHealth:
    def test_ok(self, provider, gemini_mod) -> None:
        r = mock.Mock()
        r.is_error = False
        with mock.patch.object(gemini_mod.httpx, "get", return_value=r) as mget:
            result = provider.health()
        assert result["status"] == "ok"
        assert mget.call_args[0][0] == (
            "https://generativelanguage.googleapis.com/v1beta/models/mi-modelo"
        )
        assert mget.call_args.kwargs["headers"]["x-goog-api-key"] == "secret-val"

    def test_http_error(self, provider, gemini_mod) -> None:
        r = mock.Mock()
        r.is_error = True
        r.status_code = 500
        r.text = "server error"
        with mock.patch.object(gemini_mod.httpx, "get", return_value=r):
            result = provider.health()
        assert result["status"] == "error"
        assert result["detail"] == "server error"

    def test_exception(self, provider, gemini_mod) -> None:
        with mock.patch.object(gemini_mod.httpx, "get", side_effect=httpx.RequestError("conn")):
            result = provider.health()
        assert result["status"] == "error"
        assert "conn" in result["detail"]

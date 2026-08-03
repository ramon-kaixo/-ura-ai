"""Tests para motor.core.llm.openai (OpenAIProvider)."""
from __future__ import annotations

from unittest import mock

import httpx
import pytest

from motor.core.llm.openai import OpenAIProvider  # noqa: F401  (import sanity)


@pytest.fixture()
def openai_mod():
    """Importa el módulo fresco: conftest autouse lo expulsa de sys.modules."""
    import motor.core.llm.openai

    return motor.core.llm.openai


@pytest.fixture()
def provider(openai_mod):
    secrets = {
        "OPENAI_API_KEY": "secret-val",
        "OPENAI_BASE_URL": "https://example.com/v1",
        "OPENAI_MODEL": "mi-modelo",
        "OPENAI_EMBEDDING_MODEL": "mi-embed",
        "OPENAI_TIMEOUT": "60",
        "OPENAI_TEMPERATURE": "0.9",
        "OPENAI_MAX_TOKENS": "512",
    }

    def _get(name, default=None):
        return secrets.get(name, default)

    with mock.patch.object(openai_mod, "get_secret", side_effect=_get):
        return openai_mod.OpenAIProvider()


class TestInit:
    def test_capabilities(self, provider):
        caps = provider.capabilities
        assert caps["chat"] is True
        assert caps["multimodal"] is True
        assert caps["max_context"] == 128000
        assert caps["max_output"] == 16384

    def test_defaults(self, openai_mod):
        with mock.patch.object(
            openai_mod, "get_secret", side_effect=lambda name, default=None: default
        ):
            p = openai_mod.OpenAIProvider()
        assert p._base_url == "https://api.openai.com/v1"
        assert p._model == "gpt-4o-mini"
        assert p._embedding_model == "text-embedding-3-small"
        assert p._timeout == 120
        assert p._temperature == 0.3
        assert p._max_tokens == 1024

    def test_custom_values(self, openai_mod):
        secrets = {
            "OPENAI_API_KEY": "k",
            "OPENAI_BASE_URL": "https://example.com/v1/",
            "OPENAI_MODEL": "mi-modelo",
            "OPENAI_EMBEDDING_MODEL": "mi-embed",
            "OPENAI_TIMEOUT": "60",
            "OPENAI_TEMPERATURE": "0.9",
            "OPENAI_MAX_TOKENS": "512",
        }

        def _get(name, default=None):
            return secrets.get(name, default)

        with mock.patch.object(openai_mod, "get_secret", side_effect=_get):
            p = openai_mod.OpenAIProvider()
        assert p._base_url == "https://example.com/v1"
        assert p._model == "mi-modelo"
        assert p._timeout == 60
        assert p._temperature == 0.9
        assert p._max_tokens == 512

    def test_headers(self, provider):
        headers = provider._headers()
        assert headers["Authorization"] == "Bearer secret-val"
        assert headers["Content-Type"] == "application/json"


class TestGenerate:
    def _response(self, content: str = "hola") -> mock.Mock:
        r = mock.Mock()
        r.status_code = 200
        r.json.return_value = {
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        return r

    def test_success(self, provider, openai_mod):
        with mock.patch.object(openai_mod.httpx, "post", return_value=self._response()):
            result = provider.generate("prompt")
        assert result == "hola"

    def test_request_payload(self, provider, openai_mod):
        with mock.patch.object(openai_mod.httpx, "post", return_value=self._response()) as post:
            provider.generate("p", model="m1", options={"max_tokens": 99})
        payload = post.call_args.kwargs["json"]
        assert payload["model"] == "m1"
        assert payload["messages"] == [{"role": "user", "content": "p"}]
        assert payload["temperature"] == 0.9
        assert payload["max_tokens"] == 99
        assert post.call_args.kwargs["headers"]["Authorization"] == "Bearer secret-val"

    def test_timeout(self, provider, openai_mod):
        with mock.patch.object(
            openai_mod.httpx, "post", side_effect=httpx.TimeoutException("t")
        ):
            result = provider.generate("p")
        assert "tiempo de espera" in result

    def test_http_error(self, provider, openai_mod):
        error = httpx.HTTPStatusError(
            "bad", request=mock.Mock(), response=mock.Mock(status_code=429)
        )
        with mock.patch.object(openai_mod.httpx, "post", side_effect=error):
            result = provider.generate("p")
        assert "429" in result

    def test_request_error(self, provider, openai_mod):
        with mock.patch.object(
            openai_mod.httpx, "post", side_effect=httpx.RequestError("conn")
        ):
            result = provider.generate("p")
        assert "No se pudo conectar" in result

    def test_unexpected_error(self, provider, openai_mod):
        with mock.patch.object(openai_mod.httpx, "post", side_effect=RuntimeError("boom")):
            result = provider.generate("p")
        assert "Error interno" in result


class TestEmbed:
    def _batch_response(self) -> mock.Mock:
        r = mock.Mock()
        r.status_code = 200
        r.json.return_value = {"data": [{"embedding": [0.1]}, {"embedding": [0.2]}]}
        return r

    def test_batch_success(self, provider, openai_mod):
        with mock.patch.object(openai_mod.httpx, "post", return_value=self._batch_response()):
            result = provider.embed(["a", "b"])
        assert result == [[0.1], [0.2]]

    def test_fallback_individual(self, provider, openai_mod):
        individual = mock.Mock()
        individual.status_code = 200
        individual.json.return_value = {"data": [{"embedding": [0.5]}]}
        with mock.patch.object(
            openai_mod.httpx, "post", side_effect=[httpx.RequestError("conn"), individual]
        ):
            result = provider.embed(["a"])
        assert result == [[0.5]]

    def test_individual_failure_zero_fallback(self, provider, openai_mod):
        with mock.patch.object(
            openai_mod.httpx, "post", side_effect=httpx.RequestError("conn")
        ):
            result = provider.embed(["a"])
        assert result == [[0.0] * 1536]

    def test_custom_model_no_warning_retry(self, provider, openai_mod):
        individual = mock.Mock()
        individual.status_code = 200
        individual.json.return_value = {"data": [{"embedding": [0.5]}]}
        with mock.patch.object(
            openai_mod.httpx, "post", side_effect=[RuntimeError("boom"), individual]
        ):
            result = provider.embed(["a"], model="custom")
        assert result == [[0.5]]


class TestEmbedAsync:
    def _client(self, *, status: int = 200, json_data: dict) -> mock.AsyncMock:
        client = mock.AsyncMock()
        client.post.return_value = mock.MagicMock(status_code=status, json=mock.MagicMock(return_value=json_data))
        return client

    @pytest.mark.asyncio
    async def test_batch_success(self, provider, openai_mod):
        client = self._client(json_data={"data": [{"embedding": [0.1]}]})
        ctx = mock.MagicMock()
        ctx.__aenter__.return_value = client
        with mock.patch.object(openai_mod.httpx, "AsyncClient", return_value=ctx):
            result = await provider.embed_async(["a"])
        assert result == [[0.1]]

    @pytest.mark.asyncio
    async def test_fallback_individual(self, provider, openai_mod):
        client = mock.AsyncMock()
        client.post.side_effect = httpx.RequestError("conn")
        batch_ctx = mock.MagicMock()
        batch_ctx.__aenter__.return_value = client
        ind_ctx = mock.MagicMock()
        ind_ctx.__aenter__.return_value = self._client(json_data={"data": [{"embedding": [0.7]}]})
        with mock.patch.object(
            openai_mod.httpx, "AsyncClient", side_effect=[batch_ctx, ind_ctx]
        ):
            result = await provider.embed_async(["a"])
        assert result == [[0.7]]

    @pytest.mark.asyncio
    async def test_individual_failure_zero_fallback(self, provider, openai_mod):
        client = mock.AsyncMock()
        client.post.side_effect = httpx.RequestError("conn")
        batch_ctx = mock.MagicMock()
        batch_ctx.__aenter__.return_value = client
        with mock.patch.object(
            openai_mod.httpx, "AsyncClient", return_value=batch_ctx
        ):
            result = await provider.embed_async(["a"])
        assert result == [[0.0] * 1536]


class TestHealth:
    def _ok_response(self) -> mock.Mock:
        r = mock.Mock()
        r.is_error = False
        r.json.return_value = {"data": [{"id": "gpt-4o"}, {"id": "gpt-4o-mini"}]}
        return r

    def test_ok(self, provider, openai_mod):
        with mock.patch.object(openai_mod.httpx, "get", return_value=self._ok_response()):
            result = provider.health()
        assert result["status"] == "ok"
        assert result["modelos_disponibles"] == ["gpt-4o", "gpt-4o-mini"]

    def test_http_error(self, provider, openai_mod):
        r = mock.Mock()
        r.is_error = True
        r.status_code = 500
        r.text = "server error"
        with mock.patch.object(openai_mod.httpx, "get", return_value=r):
            result = provider.health()
        assert result["status"] == "error"
        assert result["detail"] == "server error"

    def test_exception(self, provider, openai_mod):
        with mock.patch.object(
            openai_mod.httpx, "get", side_effect=httpx.RequestError("conn")
        ):
            result = provider.health()
        assert result["status"] == "error"
        assert "conn" in result["detail"]

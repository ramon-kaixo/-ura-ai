"""Tests para motor.core.llm.anthropic (AnthropicProvider).

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
def anthropic_mod():
    import motor.core.llm.anthropic

    return motor.core.llm.anthropic


@pytest.fixture()
def provider(anthropic_mod):
    secrets = {
        "ANTHROPIC_API_KEY": "secret-val",
        "ANTHROPIC_BASE_URL": "https://example.com/v1",
        "ANTHROPIC_MODEL": "mi-modelo",
        "ANTHROPIC_TIMEOUT": "60",
        "ANTHROPIC_TEMPERATURE": "0.9",
        "ANTHROPIC_MAX_TOKENS": "512",
    }

    def _get(name: str, default: str | None = None):
        return secrets.get(name, default)

    with mock.patch.object(anthropic_mod, "get_secret", side_effect=_get):
        return anthropic_mod.AnthropicProvider()


class TestInit:
    def test_capabilities(self, provider) -> None:
        caps = provider.capabilities
        assert caps["chat"] is True
        assert caps["embeddings"] is False
        assert caps["streaming"] is True
        assert caps["tools"] is True
        assert caps["multimodal"] is True
        assert caps["vision"] is True
        assert caps["max_context"] == 200000
        assert caps["max_output"] == 8192

    def test_defaults(self, anthropic_mod) -> None:
        with mock.patch.object(anthropic_mod, "get_secret", side_effect=lambda name, default=None: default):
            p = anthropic_mod.AnthropicProvider()
        assert p._base_url == "https://api.anthropic.com/v1"
        assert p._model == "claude-sonnet-4-20250514"
        assert p._timeout == 120
        assert p._temperature == 0.3
        assert p._max_tokens == 1024

    def test_custom_values(self, anthropic_mod) -> None:
        secrets = {
            "ANTHROPIC_API_KEY": "k",
            "ANTHROPIC_BASE_URL": "https://example.com/v1/",
            "ANTHROPIC_MODEL": "mi-modelo",
            "ANTHROPIC_TIMEOUT": "60",
            "ANTHROPIC_TEMPERATURE": "0.9",
            "ANTHROPIC_MAX_TOKENS": "512",
        }

        def _get(name: str, default: str | None = None):
            return secrets.get(name, default)

        with mock.patch.object(anthropic_mod, "get_secret", side_effect=_get):
            p = anthropic_mod.AnthropicProvider()
        assert p._base_url == "https://example.com/v1"
        assert p._model == "mi-modelo"
        assert p._timeout == 60
        assert p._temperature == 0.9
        assert p._max_tokens == 512

    def test_headers(self, provider) -> None:
        headers = provider._headers()
        assert headers["x-api-key"] == "secret-val"
        assert headers["anthropic-version"] == "2023-06-01"
        assert headers["Content-Type"] == "application/json"


class TestGenerate:
    def _response(self, blocks: list[dict] | None = None, usage: dict | None = None) -> mock.Mock:
        r = mock.Mock()
        r.status_code = 200
        default_blocks = [{"type": "text", "text": "hola"}]
        r.json.return_value = {
            "content": default_blocks if blocks is None else blocks,
            "usage": usage or {"input_tokens": 10, "output_tokens": 5},
        }
        return r

    def test_success(self, provider, anthropic_mod) -> None:
        with mock.patch.object(anthropic_mod.httpx, "post", return_value=self._response()) as post:
            result = provider.generate("prompt")
        assert result == "hola"
        assert post.call_args[0][0] == "https://example.com/v1/messages"
        payload = post.call_args.kwargs["json"]
        assert payload["model"] == "mi-modelo"
        assert payload["messages"] == [{"role": "user", "content": "prompt"}]
        assert payload["temperature"] == 0.9
        assert payload["max_tokens"] == 512
        assert post.call_args.kwargs["headers"]["x-api-key"] == "secret-val"
        assert post.call_args.kwargs["timeout"] == 60

    def test_success_strip_y_usage(self, provider, anthropic_mod) -> None:
        """Respuesta con espacios se trima; log_call recibe usage tokens."""
        with (
            mock.patch.object(anthropic_mod, "log_call") as log_mock,
            mock.patch.object(
                anthropic_mod.httpx, "post", return_value=self._response([{"type": "text", "text": "  x  "}])
            ),
        ):
            result = provider.generate("p")
        assert result == "x"
        assert log_mock.call_args.kwargs["input_tokens"] == 10
        assert log_mock.call_args.kwargs["output_tokens"] == 5

    def test_options_custom(self, provider, anthropic_mod) -> None:
        """Options custom respetan temperature custom y default max_tokens."""
        with mock.patch.object(anthropic_mod.httpx, "post", return_value=self._response()) as post:
            provider.generate("p", options={"temperature": 0.1, "extra": 1})
        payload = post.call_args.kwargs["json"]
        assert payload["temperature"] == 0.1
        assert payload["max_tokens"] == 512
        assert payload["extra"] == 1

    def test_concatenates_text_blocks(self, provider, anthropic_mod) -> None:
        blocks = [{"type": "text", "text": "hola "}, {"type": "text", "text": "mundo"}]
        with mock.patch.object(anthropic_mod.httpx, "post", return_value=self._response(blocks)):
            result = provider.generate("p")
        assert result == "hola mundo"

    def test_ignores_non_text_blocks(self, provider, anthropic_mod) -> None:
        blocks = [{"type": "tool_use", "name": "x"}, {"type": "text", "text": "ok"}]
        with mock.patch.object(anthropic_mod.httpx, "post", return_value=self._response(blocks)):
            result = provider.generate("p")
        assert result == "ok"

    def test_sin_contenido(self, provider, anthropic_mod) -> None:
        with mock.patch.object(anthropic_mod.httpx, "post", return_value=self._response([])):
            result = provider.generate("p")
        assert result == "El modelo no generó ninguna respuesta."

    def test_custom_model(self, provider, anthropic_mod) -> None:
        with mock.patch.object(anthropic_mod.httpx, "post", return_value=self._response()) as post:
            provider.generate("p", model="claude-x")
        assert post.call_args.kwargs["json"]["model"] == "claude-x"

    def test_timeout(self, provider, anthropic_mod) -> None:
        with mock.patch.object(anthropic_mod.httpx, "post", side_effect=httpx.TimeoutException("t")):
            result = provider.generate("p")
        assert "tiempo de espera" in result

    def test_http_error(self, provider, anthropic_mod) -> None:
        error = httpx.HTTPStatusError("bad", request=mock.Mock(), response=mock.Mock(status_code=429))
        with mock.patch.object(anthropic_mod.httpx, "post", side_effect=error):
            result = provider.generate("p")
        assert "429" in result

    def test_request_error(self, provider, anthropic_mod) -> None:
        with mock.patch.object(anthropic_mod.httpx, "post", side_effect=httpx.RequestError("conn")):
            result = provider.generate("p")
        assert "No se pudo conectar" in result

    def test_unexpected_error(self, provider, anthropic_mod) -> None:
        with mock.patch.object(anthropic_mod.httpx, "post", side_effect=RuntimeError("boom")):
            result = provider.generate("p")
        assert "Error interno" in result


class TestEmbed:
    def test_no_soportado_degradado(self, provider) -> None:
        result = provider.embed(["a", "b"])
        assert result == [[0.0] * FALLBACK_EMBEDDING_DIMENSION, [0.0] * FALLBACK_EMBEDDING_DIMENSION]

    def test_embed_async_degradado(self, provider) -> None:
        result = asyncio.run(provider.embed_async(["a"]))
        assert result == [[0.0] * FALLBACK_EMBEDDING_DIMENSION]


class TestHealth:
    def _ok_response(self) -> mock.Mock:
        r = mock.Mock()
        r.is_error = False
        r.json.return_value = {"data": [{"id": "claude-sonnet"}, {"id": "claude-opus"}]}
        return r

    def test_ok(self, provider, anthropic_mod) -> None:
        with mock.patch.object(anthropic_mod.httpx, "get", return_value=self._ok_response()) as mget:
            result = provider.health()
        assert result["status"] == "ok"
        assert result["modelos_disponibles"] == ["claude-sonnet", "claude-opus"]
        assert mget.call_args[0][0] == "https://example.com/v1/models"
        assert mget.call_args.kwargs["headers"]["anthropic-version"] == "2023-06-01"
        assert result["provider"] == "anthropic"
        assert result["latency_ms"] >= 0
        assert mget.call_args.kwargs["timeout"] == 5

    def test_http_error(self, provider, anthropic_mod) -> None:
        r = mock.Mock()
        r.is_error = True
        r.status_code = 500
        r.text = "server error"
        with mock.patch.object(anthropic_mod.httpx, "get", return_value=r):
            result = provider.health()
        assert result["status"] == "error"
        assert result["detail"] == "server error"

    def test_exception(self, provider, anthropic_mod) -> None:
        with mock.patch.object(anthropic_mod.httpx, "get", side_effect=httpx.RequestError("conn")):
            result = provider.health()
        assert result["status"] == "error"
        assert "conn" in result["detail"]

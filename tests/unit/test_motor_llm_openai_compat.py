"""Tests para proveedores LLM OpenAI-compatibles: lmstudio, vllm, openrouter.

Los tres módulos comparten estructura (generate/embed/health)
se parametrizan
sobre la clase, prefijo de secretos y defaults de cada proveedor.
"""
from __future__ import annotations

import asyncio
from unittest import mock

import httpx
import pytest

from motor.core.llm.base import FALLBACK_EMBEDDING_DIMENSION

CLASSES = {
    "lmstudio": "LMStudioProvider",
    "vllm": "VLLMProvider",
    "openrouter": "OpenRouterProvider",
}

PROVIDER_PARAMS = [
    pytest.param(
        ("lmstudio", "LMSTUDIO", "http://localhost:1234/v1", "local-model", False),
        id="lmstudio",
    ),
    pytest.param(
        ("vllm", "VLLM", "http://localhost:8000/v1", "local-model", False),
        id="vllm",
    ),
    pytest.param(
        ("openrouter", "OPENROUTER", "https://openrouter.ai/api/v1", "openrouter/auto", True),
        id="openrouter",
    ),
]


@pytest.fixture(params=PROVIDER_PARAMS)
def spec(request: pytest.FixtureRequest) -> dict:
    name, prefix, default_url, default_model, has_key = request.param
    return {
        "name": name,
        "prefix": prefix,
        "default_url": default_url,
        "default_model": default_model,
        "has_key": has_key,
    }


@pytest.fixture()
def llm_mod(spec: dict):
    """Importa el módulo fresco: conftest autouse lo expulsa de sys.modules."""
    import importlib

    return importlib.import_module(f"motor.core.llm.{spec['name']}")


@pytest.fixture()
def provider(spec: dict, llm_mod):
    prefix = spec["prefix"]
    secrets = {
        f"{prefix}_API_KEY": "secret-val",
        f"{prefix}_BASE_URL": "https://example.com/v1",
        f"{prefix}_MODEL": "mi-modelo",
        f"{prefix}_TIMEOUT": "60",
        f"{prefix}_TEMPERATURE": "0.9",
        f"{prefix}_MAX_TOKENS": "512",
    }

    def _get(name: str, default: str | None = None):
        return secrets.get(name, default)

    with mock.patch.object(llm_mod, "get_secret", side_effect=_get):
        return getattr(llm_mod, CLASSES[spec["name"]])()


class TestInit:
    def test_capabilities(self, provider) -> None:
        caps = provider.capabilities
        assert caps["chat"] is True
        assert caps["embeddings"] is True
        assert caps["streaming"] is True
        assert caps["json_mode"] is True
        assert caps["max_context"] > 0

    def test_capabilities_multimodal(self, spec: dict, provider) -> None:
        assert provider.capabilities["multimodal"] is spec["has_key"]
        assert provider.capabilities["tools"] is spec["has_key"]
        assert provider.capabilities["vision"] is spec["has_key"]

    def test_defaults(self, spec: dict, llm_mod) -> None:
        with mock.patch.object(llm_mod, "get_secret", side_effect=lambda name, default=None: default):
            p = getattr(llm_mod, CLASSES[spec["name"]])()
        assert p._base_url == spec["default_url"]
        assert p._model == spec["default_model"]
        assert p._timeout == 120
        assert p._temperature == 0.3
        assert p._max_tokens == 1024

    def test_custom_values(self, spec: dict, llm_mod) -> None:
        prefix = spec["prefix"]
        secrets = {
            f"{prefix}_BASE_URL": "https://example.com/v1/",
            f"{prefix}_MODEL": "mi-modelo",
            f"{prefix}_TIMEOUT": "60",
            f"{prefix}_TEMPERATURE": "0.9",
            f"{prefix}_MAX_TOKENS": "512",
        }

        def _get(name: str, default: str | None = None):
            return secrets.get(name, default)

        with mock.patch.object(llm_mod, "get_secret", side_effect=_get):
            p = getattr(llm_mod, CLASSES[spec["name"]])()
        assert p._base_url == "https://example.com/v1"
        assert p._model == "mi-modelo"
        assert p._timeout == 60
        assert p._temperature == 0.9
        assert p._max_tokens == 512

    def test_headers(self, spec: dict, provider) -> None:
        headers = provider._headers()
        assert headers["Content-Type"] == "application/json"
        if spec["has_key"]:
            assert headers["Authorization"] == "Bearer secret-val"
        else:
            assert "Authorization" not in headers


class TestGenerate:
    def _response(self, content: str = "hola") -> mock.Mock:
        r = mock.Mock()
        r.status_code = 200
        r.json.return_value = {
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        return r

    def test_success(self, provider, llm_mod) -> None:
        with mock.patch.object(llm_mod.httpx, "post", return_value=self._response("  hola  ")):
            result = provider.generate("prompt")
        assert result == "hola"

    def test_request_payload(self, spec: dict, provider, llm_mod) -> None:
        with mock.patch.object(llm_mod.httpx, "post", return_value=self._response()) as post:
            provider.generate("p", model="m1", options={"max_tokens": 99})
        payload = post.call_args.kwargs["json"]
        assert payload["model"] == "m1"
        assert payload["messages"] == [{"role": "user", "content": "p"}]
        assert payload["temperature"] == 0.9
        assert payload["max_tokens"] == 99
        url = post.call_args[0][0]
        assert url == f"{provider._base_url}/chat/completions"
        if spec["has_key"]:
            assert post.call_args.kwargs["headers"]["Authorization"] == "Bearer secret-val"

    def test_options_model_filtered(self, spec: dict, provider, llm_mod) -> None:
        if not spec["has_key"]:
            pytest.skip("solo openrouter filtra 'model' de options")
        with mock.patch.object(llm_mod.httpx, "post", return_value=self._response()) as post:
            provider.generate("p", options={"model": "drop-me", "temperature": 0.1})
        payload = post.call_args.kwargs["json"]
        assert "drop-me" not in payload.values()
        assert payload["temperature"] == 0.1

    def test_timeout(self, provider, llm_mod) -> None:
        with mock.patch.object(llm_mod.httpx, "post", side_effect=httpx.TimeoutException("t")):
            result = provider.generate("p")
        assert "tiempo de espera" in result

    def test_http_error(self, provider, llm_mod) -> None:
        error = httpx.HTTPStatusError("bad", request=mock.Mock(), response=mock.Mock(status_code=429))
        with mock.patch.object(llm_mod.httpx, "post", side_effect=error):
            result = provider.generate("p")
        assert "429" in result

    def test_request_error(self, provider, llm_mod) -> None:
        with mock.patch.object(llm_mod.httpx, "post", side_effect=httpx.RequestError("conn")):
            result = provider.generate("p")
        assert "No se pudo conectar" in result

    def test_unexpected_error(self, provider, llm_mod) -> None:
        with mock.patch.object(llm_mod.httpx, "post", side_effect=RuntimeError("boom")):
            result = provider.generate("p")
        assert "Error interno" in result


class TestEmbed:
    def _batch_response(self) -> mock.Mock:
        r = mock.Mock()
        r.status_code = 200
        r.json.return_value = {"data": [{"embedding": [0.1]}, {"embedding": [0.2]}]}
        return r

    def test_batch_success(self, spec: dict, provider, llm_mod) -> None:
        with mock.patch.object(llm_mod.httpx, "post", return_value=self._batch_response()) as post:
            result = provider.embed(["a", "b"])
        assert result == [[0.1], [0.2]]
        payload = post.call_args.kwargs["json"]
        assert payload["input"] == ["a", "b"]
        expected_model = "openrouter/auto" if spec["name"] == "openrouter" else "mi-modelo"
        assert payload["model"] == expected_model

    def test_custom_model(self, provider, llm_mod) -> None:
        with mock.patch.object(llm_mod.httpx, "post", return_value=self._batch_response()) as post:
            provider.embed(["a"], model="otro")
        assert post.call_args.kwargs["json"]["model"] == "otro"

    def test_request_error_zero_fallback(self, provider, llm_mod) -> None:
        with mock.patch.object(llm_mod.httpx, "post", side_effect=httpx.RequestError("conn")):
            result = provider.embed(["a"])
        assert result == [[0.0] * FALLBACK_EMBEDDING_DIMENSION]

    def test_generic_error_zero_fallback(self, provider, llm_mod) -> None:
        with mock.patch.object(llm_mod.httpx, "post", side_effect=RuntimeError("boom")):
            result = provider.embed(["a", "b"])
        assert result == [[0.0] * FALLBACK_EMBEDDING_DIMENSION, [0.0] * FALLBACK_EMBEDDING_DIMENSION]


class TestEmbedAsync:
    def _batch_response(self) -> mock.Mock:
        r = mock.Mock()
        r.status_code = 200
        r.json.return_value = {"data": [{"embedding": [0.1]}]}
        return r

    def test_batch_success(self, provider, llm_mod) -> None:
        with mock.patch.object(llm_mod.httpx, "post", return_value=self._batch_response()):
            result = asyncio.run(provider.embed_async(["a"]))
        assert result == [[0.1]]

    def test_error_zero_fallback(self, provider, llm_mod) -> None:
        with mock.patch.object(llm_mod.httpx, "post", side_effect=httpx.RequestError("conn")):
            result = asyncio.run(provider.embed_async(["a"]))
        assert result == [[0.0] * FALLBACK_EMBEDDING_DIMENSION]


class TestHealth:
    def _ok_response(self) -> mock.Mock:
        r = mock.Mock()
        r.is_error = False
        r.json.return_value = {"data": [{"id": "model-a"}, {"id": "model-b"}]}
        return r

    def test_ok(self, provider, llm_mod) -> None:
        with mock.patch.object(llm_mod.httpx, "get", return_value=self._ok_response()) as mget:
            result = provider.health()
        assert result["status"] == "ok"
        assert result["modelos_disponibles"] == ["model-a", "model-b"]
        assert mget.call_args[0][0] == f"{provider._base_url}/models"

    def test_http_error(self, provider, llm_mod) -> None:
        r = mock.Mock()
        r.is_error = True
        r.status_code = 500
        r.text = "server error"
        with mock.patch.object(llm_mod.httpx, "get", return_value=r):
            result = provider.health()
        assert result["status"] == "error"
        assert result["detail"] == "server error"

    def test_exception(self, provider, llm_mod) -> None:
        with mock.patch.object(llm_mod.httpx, "get", side_effect=httpx.RequestError("conn")):
            result = provider.health()
        assert result["status"] == "error"
        assert "conn" in result["detail"]

"""Tests para motor.core.llm.ollama (OllamaProvider)."""

from __future__ import annotations

from unittest import mock

import httpx
import pytest

from motor.core.llm.base import FALLBACK_EMBEDDING_DIMENSION


def _fake_cfg(**overrides) -> mock.Mock:
    cfg = mock.Mock()
    cfg.ollama_host = "localhost"
    cfg.ollama_port = 11434
    cfg.ollama_model = "qwen2.5:3b"
    cfg.ollama_embedding_model = "nomic-embed-text"
    cfg.ollama_timeout = 30
    cfg.ollama_temperature = 0.7
    cfg.ollama_max_tokens = 2048
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


@pytest.fixture()
def ollama_mod():
    """Importa el módulo fresco: conftest autouse lo expulsa de sys.modules."""
    import motor.core.llm.ollama

    return motor.core.llm.ollama


@pytest.fixture()
def provider(ollama_mod):
    with mock.patch.object(ollama_mod.UraConfig, "load", return_value=_fake_cfg()):
        return ollama_mod.OllamaProvider()


class TestInit:
    def test_capabilities(self, provider):
        caps = provider.capabilities
        assert caps["chat"] is True
        assert caps["embeddings"] is True
        assert caps["vision"] is True
        assert caps["multimodal"] is False
        assert caps["max_context"] == 32768

    def test_url_construction(self, provider):
        assert provider._url == "http://localhost:11434"

    def test_model_fallback_to_secret(self, ollama_mod):
        with (
            mock.patch.object(ollama_mod.UraConfig, "load", return_value=_fake_cfg(ollama_model="")),
            mock.patch("motor.core.llm.ollama.get_secret", return_value="secret-model"),
        ):
            p = ollama_mod.OllamaProvider()
        assert p._rag_model == "secret-model"

    def test_defaults_when_empty(self, ollama_mod):
        with (
            mock.patch.object(
                ollama_mod.UraConfig,
                "load",
                return_value=_fake_cfg(ollama_model="", ollama_embedding_model=""),
            ),
            mock.patch.object(ollama_mod, "get_secret", return_value=""),
        ):
            p = ollama_mod.OllamaProvider()
        assert p._rag_model == "qwen2.5:3b"
        assert p._embedding_model == "nomic-embed-text"


class TestGenerate:
    def _post_response(self, response_text: str = "hola") -> mock.Mock:
        r = mock.Mock()
        r.status_code = 200
        r.json.return_value = {"response": response_text, "eval_count": 5, "eval_duration": 1000000}
        return r

    def test_success(self, provider, ollama_mod):
        with mock.patch.object(ollama_mod.httpx, "post", return_value=self._post_response()):
            result = provider.generate("prompt")
        assert result == "hola"
        called = mock.patch.object(ollama_mod.httpx, "post").start()
        called.stop()

    def test_success_options_defaults(self, provider, ollama_mod):
        with mock.patch.object(ollama_mod.httpx, "post", return_value=self._post_response()) as post:
            provider.generate("p", model="mi-model")
        payload = post.call_args.kwargs["json"]
        assert payload["model"] == "mi-model"
        assert payload["prompt"] == "p"
        assert payload["stream"] is False
        assert payload["options"] == {"temperature": 0.7, "num_predict": 2048}

    def test_empty_response_message(self, provider, ollama_mod):
        with mock.patch.object(ollama_mod.httpx, "post", return_value=self._post_response("   ")):
            result = provider.generate("p")
        assert result == "El modelo no generó ninguna respuesta."

    def test_timeout_error(self, provider):
        with mock.patch("motor.core.llm.ollama.httpx.post", side_effect=httpx.TimeoutException("t")):
            result = provider.generate("p")
        assert result == "Error: La generación excedió el tiempo de espera."

    def test_http_status_error(self, provider, ollama_mod):
        response = mock.Mock()
        response.status_code = 503
        error = httpx.HTTPStatusError("bad", request=mock.Mock(), response=response)
        with mock.patch.object(ollama_mod.httpx, "post", side_effect=error):
            result = provider.generate("p")
        assert "503" in result

    def test_request_error(self, provider):
        with mock.patch("motor.core.llm.ollama.httpx.post", side_effect=httpx.RequestError("conn")):
            result = provider.generate("p")
        assert "No se pudo conectar" in result

    def test_unexpected_error(self, provider, ollama_mod):
        with mock.patch.object(ollama_mod.httpx, "post", side_effect=RuntimeError("boom")):
            result = provider.generate("p")
        assert "Error interno" in result


class TestEmbed:
    def _batch_response(self) -> mock.Mock:
        r = mock.Mock()
        r.status_code = 200
        r.json.return_value = {"embeddings": [[0.1, 0.2], [0.3, 0.4]]}
        return r

    def test_batch_success(self, provider, ollama_mod):
        with mock.patch.object(ollama_mod.httpx, "post", return_value=self._batch_response()):
            result = provider.embed(["a", "b"])
        assert result == [[0.1, 0.2], [0.3, 0.4]]

    def test_non_200_falls_back_to_individual(self, provider):
        batch = mock.Mock()
        batch.status_code = 500
        individual = mock.Mock()
        individual.status_code = 200
        individual.json.return_value = {"embedding": [0.5]}
        with mock.patch(
            "motor.core.llm.ollama.httpx.post",
            side_effect=[batch, individual, individual],
        ):
            result = provider.embed(["a", "b"])
        assert result == [[0.5], [0.5]]

    def test_batch_request_error_falls_back(self, provider):
        individual = mock.Mock()
        individual.status_code = 200
        individual.json.return_value = {"embedding": [0.5]}
        with mock.patch(
            "motor.core.llm.ollama.httpx.post",
            side_effect=[httpx.RequestError("conn"), individual],
        ):
            result = provider.embed(["a"])
        assert result == [[0.5]]

    def test_individual_failure_uses_fallback(self, provider):
        batch = mock.Mock()
        batch.status_code = 500
        with mock.patch(
            "motor.core.llm.ollama.httpx.post",
            side_effect=[batch, httpx.RequestError("conn")],
        ):
            result = provider.embed(["a"])
        assert result == [[0.0] * FALLBACK_EMBEDDING_DIMENSION]

    def test_batch_generic_error_falls_back(self, provider, ollama_mod):
        individual = mock.Mock()
        individual.status_code = 200
        individual.json.return_value = {"embedding": [0.5]}
        with mock.patch(
            "motor.core.llm.ollama.httpx.post",
            side_effect=[RuntimeError("boom"), individual],
        ):
            result = provider.embed(["a"])
        assert result == [[0.5]]


class TestEmbedAsync:
    def _client(self, *, status: int = 200, json_data: dict) -> mock.AsyncMock:
        client = mock.AsyncMock()
        client.post.return_value = mock.MagicMock(status_code=status, json=mock.MagicMock(return_value=json_data))
        return client

    @pytest.mark.asyncio
    async def test_batch_success(self, provider, ollama_mod):
        client = self._client(json_data={"embeddings": [[0.1]]})
        ctx = mock.MagicMock()
        ctx.__aenter__.return_value = client
        with mock.patch.object(ollama_mod.httpx, "AsyncClient", return_value=ctx):
            result = await provider.embed_async(["a"])
        assert result == [[0.1]]

    @pytest.mark.asyncio
    async def test_non_200_falls_back_to_individual(self, provider, ollama_mod):
        batch_ctx = mock.MagicMock()
        batch_ctx.__aenter__.return_value = self._client(status=500, json_data={})
        ind_ctx = mock.MagicMock()
        ind_ctx.__aenter__.return_value = self._client(json_data={"embedding": [0.7]})
        with mock.patch("motor.core.llm.ollama.httpx.AsyncClient", side_effect=[batch_ctx, ind_ctx]):
            result = await provider.embed_async(["a"])
        assert result == [[0.7]]

    @pytest.mark.asyncio
    async def test_individual_failure_uses_fallback(self, provider, ollama_mod):
        batch_ctx = mock.MagicMock()
        batch_ctx.__aenter__.return_value = self._client(status=500, json_data={})
        client = mock.AsyncMock()
        client.post.side_effect = httpx.RequestError("conn")
        ind_ctx = mock.MagicMock()
        ind_ctx.__aenter__.return_value = client
        with mock.patch("motor.core.llm.ollama.httpx.AsyncClient", side_effect=[batch_ctx, ind_ctx]):
            result = await provider.embed_async(["a"])
        assert result == [[0.0] * FALLBACK_EMBEDDING_DIMENSION]

    @pytest.mark.asyncio
    async def test_batch_request_error_falls_back(self, provider, ollama_mod):
        client = mock.AsyncMock()
        client.post.side_effect = httpx.RequestError("conn")
        batch_ctx = mock.MagicMock()
        batch_ctx.__aenter__.return_value = client
        ind_ctx = mock.MagicMock()
        ind_ctx.__aenter__.return_value = self._client(json_data={"embedding": [0.7]})
        with mock.patch("motor.core.llm.ollama.httpx.AsyncClient", side_effect=[batch_ctx, ind_ctx]):
            result = await provider.embed_async(["a"])
        assert result == [[0.7]]

    @pytest.mark.asyncio
    async def test_batch_generic_error_falls_back(self, provider, ollama_mod):
        client = mock.AsyncMock()
        client.post.side_effect = RuntimeError("boom")
        batch_ctx = mock.MagicMock()
        batch_ctx.__aenter__.return_value = client
        ind_ctx = mock.MagicMock()
        ind_ctx.__aenter__.return_value = self._client(json_data={"embedding": [0.7]})
        with mock.patch("motor.core.llm.ollama.httpx.AsyncClient", side_effect=[batch_ctx, ind_ctx]):
            result = await provider.embed_async(["a"])
        assert result == [[0.7]]


class TestHealth:
    def _ok_response(self) -> mock.Mock:
        r = mock.Mock()
        r.is_error = False
        r.json.return_value = {"models": [{"name": "qwen2.5:3b"}]}
        return r

    def test_ok(self, provider, ollama_mod):
        with mock.patch.object(ollama_mod.httpx, "get", return_value=self._ok_response()):
            result = provider.health()
        assert result["status"] == "ok"
        assert result["modelos_disponibles"] == ["qwen2.5:3b"]

    def test_http_error(self, provider, ollama_mod):
        r = mock.Mock()
        r.is_error = True
        r.status_code = 500
        r.text = "server error"
        with mock.patch.object(ollama_mod.httpx, "get", return_value=r):
            result = provider.health()
        assert result["status"] == "error"
        assert result["detail"] == "server error"

    def test_exception(self, provider):
        with mock.patch("motor.core.llm.ollama.httpx.get", side_effect=httpx.RequestError("conn")):
            result = provider.health()
        assert result["status"] == "error"
        assert "conn" in result["detail"]


class TestGenerateStream:
    def test_emite_fragmentos_reales(self, provider, ollama_mod):
        lines = [
            '{"response": "ho", "done": false}',
            '{"response": "la", "done": false}',
            '{"response": "", "done": true}',
        ]
        ctx = mock.MagicMock()
        ctx.status_code = 200
        ctx.iter_lines.return_value = iter(lines)
        ctx.__enter__.return_value = ctx
        with mock.patch.object(ollama_mod.httpx, "stream", return_value=ctx) as stream:
            resultado = list(provider.generate_stream("p", model="m"))
        assert resultado == ["ho", "la"]
        payload = stream.call_args.kwargs["json"]
        assert payload["stream"] is True
        assert payload["model"] == "m"

    def test_error_http_lanza_runtime_error(self, provider, ollama_mod):
        ctx = mock.MagicMock()
        ctx.status_code = 404
        ctx.iter_lines.return_value = iter([])
        ctx.__enter__.return_value = ctx
        with mock.patch.object(ollama_mod.httpx, "stream", return_value=ctx):
            with pytest.raises(RuntimeError, match="404"):
                list(provider.generate_stream("p"))

    def test_base_generate_stream_degrada_a_generate(self):
        from motor.core.llm.base import BaseLLMProvider

        class _ProviderSinStream(BaseLLMProvider):
            def generate(self, prompt, model=None, options=None):
                return "completo"

            def embed(self, texts, model=None):
                return [[0.0] * 768 for _ in texts]

            async def embed_async(self, texts, model=None):
                return self.embed(texts, model)

            def health(self):
                return {"status": "ok"}

        assert list(_ProviderSinStream().generate_stream("p")) == ["completo"]


class TestChatGenerate:
    def test_tools_nativos(self, provider, ollama_mod):
        r = mock.Mock()
        r.status_code = 200
        r.json.return_value = {
            "message": {
                "content": "",
                "tool_calls": [{"function": {"name": "web_search", "arguments": {"q": "x"}}}],
            },
            "prompt_eval_count": 10,
            "eval_count": 3,
        }
        with mock.patch.object(ollama_mod.httpx, "post", return_value=r) as post:
            result = provider.chat_generate(
                [{"role": "user", "content": "busca"}],
                model="m",
                tools=[{"type": "function"}],
                options={"temperature": 0.1},
            )
        payload = post.call_args.kwargs["json"]
        assert payload["stream"] is False
        assert payload["tools"] == [{"type": "function"}]
        assert payload["messages"] == [{"role": "user", "content": "busca"}]
        tc = result["tool_calls"]
        assert tc[0]["function"]["name"] == "web_search"
        assert tc[0]["id"] == "call_0"
        assert tc[0]["type"] == "function"
        assert result["usage"]["prompt_tokens"] == 10
        assert result["usage"]["completion_tokens"] == 3
        assert result["usage"]["total_tokens"] == 13

    def test_sin_tools_payload_no_lleva_clave(self, provider, ollama_mod):
        r = mock.Mock()
        r.status_code = 200
        r.json.return_value = {"message": {"content": "ok"}}
        with mock.patch.object(ollama_mod.httpx, "post", return_value=r) as post:
            result = provider.chat_generate([{"role": "user", "content": "x"}])
        assert "tools" not in post.call_args.kwargs["json"]
        assert result["content"] == "ok"
        assert result["tool_calls"] is None

    def test_error_http_lanza_runtime_error(self, provider, ollama_mod):
        r = mock.Mock()
        r.status_code = 429
        with mock.patch.object(ollama_mod.httpx, "post", return_value=r):
            with pytest.raises(RuntimeError, match="429"):
                provider.chat_generate([{"role": "user", "content": "x"}])

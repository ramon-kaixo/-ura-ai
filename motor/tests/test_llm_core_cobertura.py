"""Cobertura 100x100 de motor/core/llm (TASK-20260814-003).

Cubre openai, ollama, router, base, _state y el resto de providers con
httpx mockeado (sin red). Los tests existentes (test_llm_providers.py)
solo cubren el contrato; estos cubren ramas y errores.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Self

import httpx
import pytest

import motor.core.llm._state as state_mod
import motor.core.llm.ollama as ollama_mod
import motor.core.llm.openai as openai_mod
import motor.core.llm.registry as registry_mod
from motor.core.llm._logging import log_call, percentile
from motor.core.llm.groq import GroqProvider
from motor.core.llm.ollama import OllamaProvider
from motor.core.llm.openai import OpenAIProvider
from motor.core.llm.registry import ProviderRegistry

# ── fakes httpx ──────────────────────────────────────────────────────────────


class FakeResp:
    def __init__(self, data: dict | None = None, status: int = 200, text: str = "detalle") -> None:
        self._data = data or {}
        self.status_code = status
        self.text = text
        self.is_error = status >= 400

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"{self.status_code} error",
                request=httpx.Request("POST", "http://fake"),
                response=httpx.Response(self.status_code),
            )

    def json(self) -> dict:
        return self._data


class FakeStream:
    def __init__(self, lines: list[str], status: int = 200) -> None:
        self._lines = lines
        self.status_code = status

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *a: object) -> None:
        return None

    def iter_lines(self) -> Iterator[str]:
        yield from self._lines


class FakeAsyncClient:
    def __init__(self, responses: list[Any]) -> None:
        self._responses = list(responses)
        self.posted: list[tuple[str, dict]] = []

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *a: object) -> None:
        return None

    async def post(self, url: str, **kw: Any) -> Any:
        self.posted.append((url, kw.get("json", {})))
        if not self._responses:
            raise httpx.RequestError("no more responses")
        resp = self._responses.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return resp


def _ok_generate() -> FakeResp:
    return FakeResp(
        {
            "choices": [{"message": {"content": "  hola mundo  "}}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 5},
        }
    )


def _ok_embed(n: int = 2) -> FakeResp:
    return FakeResp({"data": [{"embedding": [0.1, 0.2]} for _ in range(n)]})


# ── openai: init y headers ──────────────────────────────────────────────────


class TestOpenAIInit:
    def test_init_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "k-test")
        p = OpenAIProvider()
        assert p._provider_name == "openai"
        assert p._base_url == "https://api.openai.com/v1"
        assert p._model == "gpt-4o-mini"
        assert p._embedding_model == "text-embedding-3-small"
        assert p._timeout == 120
        assert p._temperature == 0.3
        assert p._max_tokens == 1024
        headers = p._headers()
        assert headers["Authorization"] == "Bearer k-test"
        assert headers["Content-Type"] == "application/json"

    def test_init_custom_secrets(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "k")
        monkeypatch.setenv("OPENAI_BASE_URL", "http://local:8080/v1/")
        monkeypatch.setenv("OPENAI_MODEL", "m1")
        monkeypatch.setenv("OPENAI_EMBEDDING_MODEL", "e1")
        monkeypatch.setenv("OPENAI_TIMEOUT", "30")
        monkeypatch.setenv("OPENAI_TEMPERATURE", "0.7")
        monkeypatch.setenv("OPENAI_MAX_TOKENS", "512")
        p = OpenAIProvider()
        assert p._base_url == "http://local:8080/v1"
        assert p._model == "m1"
        assert p._embedding_model == "e1"
        assert p._timeout == 30
        assert p._temperature == 0.7
        assert p._max_tokens == 512

    def test_capabilities(self) -> None:
        caps = OpenAIProvider().capabilities
        assert caps["chat"] is True
        assert caps["embeddings"] is True
        assert caps["streaming"] is True
        assert caps["max_context"] == 128000


# ── openai: generate ────────────────────────────────────────────────────────


class TestOpenAIGenerate:
    def test_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "k")
        calls: list[dict] = []

        def fake_post(url: str, **kw: Any) -> FakeResp:
            calls.append({"url": url, "json": kw.get("json", {})})
            return _ok_generate()

        monkeypatch.setattr(openai_mod.httpx, "post", fake_post)
        p = OpenAIProvider()
        out = p.generate("hola")
        assert out == "hola mundo"
        assert calls[0]["url"] == "https://api.openai.com/v1/chat/completions"
        body = calls[0]["json"]
        assert body["model"] == "gpt-4o-mini"
        assert body["temperature"] == 0.3
        assert body["max_tokens"] == 1024

    def test_ok_model_y_options(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "k")
        calls: list[dict] = []

        def fake_post(url: str, **kw: Any) -> FakeResp:
            calls.append(kw.get("json", {}))
            return _ok_generate()

        monkeypatch.setattr(openai_mod.httpx, "post", fake_post)
        p = OpenAIProvider()
        out = p.generate("hola", model="gpt-x", options={"temperature": 0.9})
        assert out == "hola mundo"
        assert calls[0]["model"] == "gpt-x"
        assert calls[0]["temperature"] == 0.9

    def test_timeout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "k")
        monkeypatch.setattr(openai_mod.httpx, "post", lambda *a, **k: (_ for _ in ()).throw(httpx.TimeoutException("t")))
        p = OpenAIProvider()
        out = p.generate("hola")
        assert out.startswith("Error:")
        assert "tiempo" in out

    def test_http_status_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "k")
        monkeypatch.setattr(
            openai_mod.httpx,
            "post",
            lambda *a, **k: (_ for _ in ()).throw(
                httpx.HTTPStatusError(
                    "500",
                    request=httpx.Request("POST", "http://fake"),
                    response=httpx.Response(500),
                )
            ),
        )
        p = OpenAIProvider()
        out = p.generate("hola")
        assert "Error:" in out
        assert "500" in out

    def test_request_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "k")
        monkeypatch.setattr(openai_mod.httpx, "post", lambda *a, **k: (_ for _ in ()).throw(httpx.RequestError("conn")))
        p = OpenAIProvider()
        assert "conectar" in p.generate("hola")

    def test_unexpected_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "k")
        monkeypatch.setattr(openai_mod.httpx, "post", lambda *a, **k: (_ for _ in ()).throw(ValueError("boom")))
        p = OpenAIProvider()
        assert "interno" in p.generate("hola")


# ── openai: generate_stream ─────────────────────────────────────────────────


class TestOpenAIGenerateStream:
    def _lines(self) -> list[str]:
        return [
            "",
            "not data",
            "data: " + json.dumps({"choices": [{"delta": {"content": None}}]}),
            "data: " + json.dumps({"choices": [{"delta": {"content": "un"}}]}),
            "data: no-json",
            "data: " + json.dumps({"choices": [{"delta": {"content": "dos"}}]}),
            "data: [DONE]",
        ]

    def test_stream_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "k")
        monkeypatch.setattr(openai_mod.httpx, "stream", lambda *a, **k: FakeStream(self._lines()))
        p = OpenAIProvider()
        chunks = list(p.generate_stream("hola"))
        assert chunks == ["un", "dos"]

    def test_stream_http_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "k")
        monkeypatch.setattr(openai_mod.httpx, "stream", lambda *a, **k: FakeStream([], status=429))
        p = OpenAIProvider()
        with pytest.raises(RuntimeError, match="429"):
            list(p.generate_stream("hola"))

    def test_stream_sin_done(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "k")
        lines = [
            "data: " + json.dumps({"choices": [{"delta": {"content": "x"}}]}),
            "data: " + json.dumps({"choices": [{"delta": {"content": "y"}}]}),
        ]
        monkeypatch.setattr(openai_mod.httpx, "stream", lambda *a, **k: FakeStream(lines))
        p = OpenAIProvider()
        assert list(p.generate_stream("hola")) == ["x", "y"]


# ── openai: chat_generate ───────────────────────────────────────────────────


class TestOpenAIChat:
    def test_ok_con_tools(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "k")
        calls: list[dict] = []

        def fake_post(url: str, **kw: Any) -> FakeResp:
            calls.append(kw.get("json", {}))
            return FakeResp(
                {
                    "choices": [{"message": {"content": "resp", "tool_calls": [{"id": "t1"}]}}],
                    "usage": {"prompt_tokens": 1},
                }
            )

        monkeypatch.setattr(openai_mod.httpx, "post", fake_post)
        p = OpenAIProvider()
        out = p.chat_generate([{"role": "user", "content": "q"}], tools=[{"type": "function"}])
        assert out["content"] == "resp"
        assert out["tool_calls"] == [{"id": "t1"}]
        assert out["usage"]["prompt_tokens"] == 1
        assert "tools" in calls[0]

    def test_ok_sin_tools(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "k")
        calls: list[dict] = []

        def fake_post(url: str, **kw: Any) -> FakeResp:
            calls.append(kw.get("json", {}))
            return FakeResp({"choices": [{"message": {"content": None}}]})

        monkeypatch.setattr(openai_mod.httpx, "post", fake_post)
        p = OpenAIProvider()
        out = p.chat_generate([{"role": "user", "content": "q"}], model="m2")
        assert out["content"] == ""
        assert out["tool_calls"] is None
        assert "tools" not in calls[0]

    def test_http_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "k")
        monkeypatch.setattr(openai_mod.httpx, "post", lambda *a, **k: FakeResp(status=503))
        p = OpenAIProvider()
        with pytest.raises(RuntimeError, match="503"):
            p.chat_generate([{"role": "user", "content": "q"}])


# ── openai: embed y embed_async ─────────────────────────────────────────────


class TestOpenAIEmbed:
    def test_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "k")
        calls: list[dict] = []

        def fake_post(url: str, **kw: Any) -> FakeResp:
            calls.append(kw.get("json", {}))
            return _ok_embed(2)

        monkeypatch.setattr(openai_mod.httpx, "post", fake_post)
        p = OpenAIProvider()
        out = p.embed(["a", "b"])
        assert out == [[0.1, 0.2], [0.1, 0.2]]
        assert calls[0]["model"] == "text-embedding-3-small"
        assert calls[0]["input"] == ["a", "b"]

    def test_ok_model_explicito(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "k")
        calls: list[dict] = []

        def fake_post(url: str, **kw: Any) -> FakeResp:
            calls.append(kw.get("json", {}))
            return _ok_embed(1)

        monkeypatch.setattr(openai_mod.httpx, "post", fake_post)
        p = OpenAIProvider()
        out = p.embed(["a"], model="custom-embed")
        assert calls[0]["model"] == "custom-embed"
        assert len(out) == 1

    def test_fallback_modelo_distinto(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "k")
        respuestas: list[Any] = [httpx.RequestError("batch fail"), _ok_embed(1)]

        def fake_post(url: str, **kw: Any) -> FakeResp:
            resp = respuestas.pop(0)
            if isinstance(resp, Exception):
                raise resp
            return resp

        monkeypatch.setattr(openai_mod.httpx, "post", fake_post)
        p = OpenAIProvider()
        out = p.embed(["a"], model="otro-embed")
        assert out == [[0.1, 0.2]]

    def test_fallback_individual_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "k")
        respuestas: list[Any] = [httpx.RequestError("batch fail"), _ok_embed(1), _ok_embed(1)]

        def fake_post(url: str, **kw: Any) -> FakeResp:
            resp = respuestas.pop(0)
            if isinstance(resp, Exception):
                raise resp
            return resp

        monkeypatch.setattr(openai_mod.httpx, "post", fake_post)
        p = OpenAIProvider()
        out = p.embed(["a", "b"])
        assert out == [[0.1, 0.2], [0.1, 0.2]]

    def test_fallback_individual_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "k")
        respuestas: list[Any] = [httpx.RequestError("batch fail"), httpx.RequestError("one fail"), _ok_embed(1)]

        def fake_post(url: str, **kw: Any) -> FakeResp:
            resp = respuestas.pop(0)
            if isinstance(resp, Exception):
                raise resp
            return resp

        monkeypatch.setattr(openai_mod.httpx, "post", fake_post)
        p = OpenAIProvider()
        out = p.embed(["a", "b"])
        assert out == [[0.0] * 1536, [0.1, 0.2]]

    def test_embed_async_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import asyncio

        monkeypatch.setenv("OPENAI_API_KEY", "k")
        client = FakeAsyncClient([_ok_embed(2)])

        def fake_async(*a: Any, **k: Any) -> FakeAsyncClient:
            return client

        monkeypatch.setattr(openai_mod.httpx, "AsyncClient", fake_async)
        p = OpenAIProvider()
        out = asyncio.run(p.embed_async(["a", "b"]))
        assert out == [[0.1, 0.2], [0.1, 0.2]]

    def test_embed_async_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import asyncio

        monkeypatch.setenv("OPENAI_API_KEY", "k")
        client = FakeAsyncClient([httpx.RequestError("fail"), _ok_embed(1), httpx.RequestError("one fail")])

        def fake_async(*a: Any, **k: Any) -> FakeAsyncClient:
            return client

        monkeypatch.setattr(openai_mod.httpx, "AsyncClient", fake_async)
        p = OpenAIProvider()
        out = asyncio.run(p.embed_async(["a", "b"]))
        assert out == [[0.1, 0.2], [0.0] * 1536]


# ── openai: health ──────────────────────────────────────────────────────────


class TestOpenAIHealth:
    def test_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "k")
        monkeypatch.setattr(
            openai_mod.httpx,
            "get",
            lambda *a, **k: FakeResp({"data": [{"id": "gpt-4"}, {"id": "gpt-3"}]}),
        )
        p = OpenAIProvider()
        out = p.health()
        assert out["status"] == "ok"
        assert out["modelos_disponibles"] == ["gpt-4", "gpt-3"]
        assert out["latency_ms"] >= 0

    def test_is_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "k")
        monkeypatch.setattr(openai_mod.httpx, "get", lambda *a, **k: FakeResp(status=500, text="boom"))
        p = OpenAIProvider()
        out = p.health()
        assert out["status"] == "error"
        assert "boom" in out["detail"]

    def test_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "k")
        monkeypatch.setattr(openai_mod.httpx, "get", lambda *a, **k: (_ for _ in ()).throw(httpx.RequestError("x")))
        p = OpenAIProvider()
        out = p.health()
        assert out["status"] == "error"
        assert "x" in out["detail"]


# ── ollama: ramas que faltan en test_llm_providers.py ───────────────────────


class TestOllamaComplemento:
    def test_generate_stream_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OLLAMA_HOST", "http://fake:11434")
        lines = [
            json.dumps({"response": "primero"}),
            json.dumps({"response": ""}),
            json.dumps({"response": "segundo", "done": True}),
        ]

        class FakeOllamaStream:
            status_code = 200

            def __enter__(self) -> Self:
                return self

            def __exit__(self, *a: object) -> None:
                return None

            def iter_lines(self) -> Iterator[str]:
                yield from lines

        monkeypatch.setattr(ollama_mod.httpx, "stream", lambda *a, **k: FakeOllamaStream())
        p = OllamaProvider()
        chunks = list(p.generate_stream("hola"))
        assert "primero" in chunks
        assert "segundo" in chunks

    def test_health_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OLLAMA_HOST", "http://fake:11434")
        monkeypatch.setattr(
            ollama_mod.httpx,
            "get",
            lambda *a, **k: FakeResp({"models": [{"name": "llama3"}, {"name": "qwen"}]}),
        )
        p = OllamaProvider()
        out = p.health()
        assert out["status"] == "ok"
        assert "llama3" in out["modelos_disponibles"]

    def test_health_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OLLAMA_HOST", "http://fake:11434")
        monkeypatch.setattr(ollama_mod.httpx, "get", lambda *a, **k: FakeResp(status=500))
        p = OllamaProvider()
        out = p.health()
        assert out["status"] == "error"

    def test_embed_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OLLAMA_HOST", "http://fake:11434")
        monkeypatch.setattr(
            ollama_mod.httpx,
            "post",
            lambda *a, **k: FakeResp({"embeddings": [[0.5, 0.5], [0.6, 0.6]]}),
        )
        p = OllamaProvider()
        out = p.embed(["a", "b"])
        assert out == [[0.5, 0.5], [0.6, 0.6]]


class TestOllamaGenerate:
    def test_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[dict] = []

        def fake_post(url: str, **kw: Any) -> FakeResp:
            calls.append(kw.get("json", {}))
            return FakeResp({"response": "  respuesta  ", "eval_count": 7, "eval_duration": 1_000_000})

        monkeypatch.setattr(ollama_mod.httpx, "post", fake_post)
        p = OllamaProvider()
        assert p.generate("hola") == "respuesta"
        assert calls[0]["stream"] is False
        assert calls[0]["options"]["temperature"] == p._temperature
        assert calls[0]["options"]["num_predict"] == p._max_tokens

    def test_ok_respuesta_vacia(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(ollama_mod.httpx, "post", lambda *a, **k: FakeResp({"response": "   "}))
        p = OllamaProvider()
        assert p.generate("hola") == "El modelo no generó ninguna respuesta."

    def test_timeout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            ollama_mod.httpx, "post", lambda *a, **k: (_ for _ in ()).throw(httpx.TimeoutException("t"))
        )
        p = OllamaProvider()
        assert "tiempo" in p.generate("hola")

    def test_http_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            ollama_mod.httpx,
            "post",
            lambda *a, **k: (_ for _ in ()).throw(
                httpx.HTTPStatusError(
                    "500", request=httpx.Request("POST", "http://fake"), response=httpx.Response(500)
                )
            ),
        )
        p = OllamaProvider()
        assert "500" in p.generate("hola")

    def test_connection_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(ollama_mod.httpx, "post", lambda *a, **k: (_ for _ in ()).throw(httpx.RequestError("x")))
        p = OllamaProvider()
        assert "conectar" in p.generate("hola")

    def test_unexpected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(ollama_mod.httpx, "post", lambda *a, **k: (_ for _ in ()).throw(ValueError("boom")))
        p = OllamaProvider()
        assert "interno" in p.generate("hola")

    def test_capabilities(self) -> None:
        caps = OllamaProvider().capabilities
        assert caps["chat"] is True
        assert caps["tools"] is True
        assert caps["vision"] is True


class TestOllamaStreamErrores:
    def test_http_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class Bad:
            status_code = 500

            def __enter__(self) -> Self:
                return self

            def __exit__(self, *a: object) -> None:
                return None

            def iter_lines(self) -> Iterator[str]:
                return iter([])

        monkeypatch.setattr(ollama_mod.httpx, "stream", lambda *a, **k: Bad())
        p = OllamaProvider()
        with pytest.raises(RuntimeError, match="500"):
            list(p.generate_stream("hola"))

    def test_linea_vacia_sin_done(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class S:
            status_code = 200

            def __enter__(self) -> Self:
                return self

            def __exit__(self, *a: object) -> None:
                return None

            def iter_lines(self) -> Iterator[str]:
                return iter(["", '{"response": "a"}', '{"response": ""}'])

        monkeypatch.setattr(ollama_mod.httpx, "stream", lambda *a, **k: S())
        p = OllamaProvider()
        assert list(p.generate_stream("hola")) == ["a"]


class TestOllamaChat:
    def test_ok_sin_tools(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[dict] = []

        def fake_post(url: str, **kw: Any) -> FakeResp:
            calls.append(kw.get("json", {}))
            return FakeResp({"message": {"content": "chat ok"}, "prompt_eval_count": 2, "eval_count": 4})

        monkeypatch.setattr(ollama_mod.httpx, "post", fake_post)
        p = OllamaProvider()
        out = p.chat_generate([{"role": "user", "content": "q"}])
        assert out["content"] == "chat ok"
        assert out["tool_calls"] is None
        assert out["usage"]["total_tokens"] == 6
        assert "tools" not in calls[0]

    def test_ok_con_tools(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[dict] = []

        def fake_post(url: str, **kw: Any) -> FakeResp:
            calls.append(kw.get("json", {}))
            return FakeResp(
                {
                    "message": {
                        "content": "",
                        "tool_calls": [{"function": {"name": "f1", "arguments": {"x": 1}}}],
                    }
                }
            )

        monkeypatch.setattr(ollama_mod.httpx, "post", fake_post)
        p = OllamaProvider()
        out = p.chat_generate([{"role": "user", "content": "q"}], tools=[{"type": "function"}])
        assert out["tool_calls"][0]["function"]["arguments"] == {"x": 1}
        assert "tools" in calls[0]

    def test_http_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(ollama_mod.httpx, "post", lambda *a, **k: FakeResp(status=429))
        p = OllamaProvider()
        with pytest.raises(RuntimeError, match="429"):
            p.chat_generate([{"role": "user", "content": "q"}])


class TestOllamaNormalizarToolCalls:
    def test_args_dict(self) -> None:
        out = OllamaProvider._normalizar_tool_calls([{"id": "a", "function": {"name": "n", "arguments": {"k": 1}}}])
        assert out[0]["id"] == "a"
        assert out[0]["function"]["arguments"] == {"k": 1}

    def test_args_str_valido(self) -> None:
        out = OllamaProvider._normalizar_tool_calls([{"function": {"arguments": '{"k": 2}'}}])
        assert out[0]["function"]["arguments"]["k"] == 2
        assert out[0]["id"].startswith("call_")

    def test_args_str_invalido(self) -> None:
        out = OllamaProvider._normalizar_tool_calls([{"function": {"arguments": "no-json"}}])
        assert out[0]["function"]["arguments"] == {"raw": "no-json"}


class TestOllamaEmbedFallback:
    def test_status_no_200_batch(self, monkeypatch: pytest.MonkeyPatch) -> None:
        respuestas: list[Any] = [FakeResp(status=500), FakeResp({"embedding": [0.7]})]

        def fake_post(url: str, **kw: Any) -> FakeResp:
            resp = respuestas.pop(0)
            if isinstance(resp, Exception):
                raise resp
            return resp

        monkeypatch.setattr(ollama_mod.httpx, "post", fake_post)
        p = OllamaProvider()
        out = p.embed(["a"])
        assert out == [[0.7]]

    def test_request_error_batch(self, monkeypatch: pytest.MonkeyPatch) -> None:
        respuestas: list[Any] = [httpx.RequestError("conn"), FakeResp({"embedding": [0.1]})]

        def fake_post(url: str, **kw: Any) -> FakeResp:
            resp = respuestas.pop(0)
            if isinstance(resp, Exception):
                raise resp
            return resp

        monkeypatch.setattr(ollama_mod.httpx, "post", fake_post)
        p = OllamaProvider()
        assert p.embed(["a"]) == [[0.1]]

    def test_exception_batch_y_individual(self, monkeypatch: pytest.MonkeyPatch) -> None:
        respuestas: list[Any] = [ValueError("boom"), httpx.RequestError("one")]

        def fake_post(url: str, **kw: Any) -> FakeResp:
            resp = respuestas.pop(0)
            if isinstance(resp, Exception):
                raise resp
            return resp

        monkeypatch.setattr(ollama_mod.httpx, "post", fake_post)
        p = OllamaProvider()
        out = p.embed(["a", "b"])
        assert out == [[0.0] * 768, [0.0] * 768]

    def test_embed_async_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import asyncio

        client = FakeAsyncClient([FakeResp({"embeddings": [[0.5, 0.5]]})])
        monkeypatch.setattr(ollama_mod.httpx, "AsyncClient", lambda *a, **k: client)
        p = OllamaProvider()
        assert asyncio.run(p.embed_async(["a"])) == [[0.5, 0.5]]

    def test_embed_async_status_no_200(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import asyncio

        client = FakeAsyncClient([FakeResp(status=500), FakeResp({"embedding": [0.2]})])
        monkeypatch.setattr(ollama_mod.httpx, "AsyncClient", lambda *a, **k: client)
        p = OllamaProvider()
        assert asyncio.run(p.embed_async(["a"])) == [[0.2]]

    def test_embed_async_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import asyncio

        client = FakeAsyncClient([httpx.RequestError("x"), httpx.RequestError("y")])
        monkeypatch.setattr(ollama_mod.httpx, "AsyncClient", lambda *a, **k: client)
        p = OllamaProvider()
        assert asyncio.run(p.embed_async(["a"])) == [[0.0] * 768]

    def test_embed_async_exception_generica(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import asyncio

        client = FakeAsyncClient([ValueError("boom"), httpx.RequestError("y")])
        monkeypatch.setattr(ollama_mod.httpx, "AsyncClient", lambda *a, **k: client)
        p = OllamaProvider()
        assert asyncio.run(p.embed_async(["a"])) == [[0.0] * 768]


# ── _logging.py ─────────────────────────────────────────────────────────────


class TestLogging:
    def test_percentile_vacio(self) -> None:
        assert percentile([], 50) == 0.0

    def test_percentile_ok(self) -> None:
        assert percentile([1.0, 2.0, 3.0, 4.0], 50) == 3.0
        assert percentile([5.0], 99) == 5.0
        assert percentile([1.0, 2.0], 0) == 1.0

    def test_log_call_con_error(self, caplog: pytest.LogCaptureFixture) -> None:
        import logging

        with caplog.at_level(logging.WARNING):
            log_call("p", "m", 12.3, "timeout", extra1=1)
        assert any(r.levelno == logging.WARNING for r in caplog.records)
        assert any("llm_call" in r.getMessage() for r in caplog.records)
        assert any("error=timeout" in r.getMessage() for r in caplog.records)

    def test_log_call_sin_error(self, caplog: pytest.LogCaptureFixture) -> None:
        import logging

        with caplog.at_level(logging.INFO):
            log_call("p", "m", 12.3)
        assert any(r.levelno == logging.INFO for r in caplog.records)
        assert any("error=null" in r.getMessage() for r in caplog.records)


# ── __init__.py (API pública con estado lazy) ───────────────────────────────


class TestLlmApi:
    def test_generate_delega(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import motor.core.llm as llm_api

        fake = SimpleNamespace(generate=lambda *a, **k: "ok", health=lambda: {"status": "ok"})
        monkeypatch.setattr(llm_api, "_get_state", lambda: fake)
        assert llm_api.generate("p") == "ok"
        assert llm_api.health() == fake.health()

    def test_get_state_lazy(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import motor.core.llm as llm_api

        monkeypatch.setattr(llm_api, "_LLM_STATE", None)
        estado = llm_api._get_state()
        assert estado is not None
        assert llm_api._LLM_STATE is estado


# ── groq.py ─────────────────────────────────────────────────────────────────


class TestGroq:
    def test_init_y_capabilities(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GROQ_API_KEY", "k")
        p = GroqProvider()
        assert p._provider_name == "groq"
        assert p._base_url == "https://api.groq.com/openai/v1"
        assert p._model == "llama-3.1-70b-versatile"
        assert p._timeout == 60
        assert p.capabilities["embeddings"] is False

    def test_embed_y_async(self) -> None:
        p = GroqProvider()
        assert p.embed(["a", "b"]) == [[0.0] * 768, [0.0] * 768]

        import asyncio

        assert asyncio.run(p.embed_async(["a"])) == [[0.0] * 768]


# ── registry.py ─────────────────────────────────────────────────────────────


class _MiniProvider:
    def generate(self, *a: Any, **k: Any) -> str:
        return "x"


class TestRegistryCobertura:
    def test_unregister_default_con_restantes(self) -> None:
        reg = ProviderRegistry()
        reg.register("a", _MiniProvider(), default=True)
        reg.register("b", _MiniProvider())
        reg.unregister("a")
        assert reg.default_name == "b"
        assert reg.default is not None

    def test_singleton_global(self) -> None:
        assert isinstance(registry_mod.registry, ProviderRegistry)


# ── _state.py ───────────────────────────────────────────────────────────────


class TestState:
    def test_build_y_default(self) -> None:
        estado = state_mod.build_llm_state()
        assert estado.default_provider is not None
        assert estado.registry is not None


# ── anthropic.py ────────────────────────────────────────────────────────────


import motor.core.llm.anthropic as anthropic_mod
from motor.core.llm.anthropic import AnthropicProvider


class TestAnthropicCobertura:
    def test_init_headers(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
        p = AnthropicProvider()
        assert p._base_url == "https://api.anthropic.com/v1"
        assert p._model == "claude-sonnet-4-20250514"
        assert p._timeout == 120
        h = p._headers()
        assert h["x-api-key"] == "k"
        assert h["anthropic-version"] == "2023-06-01"

    def test_generate_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
        calls: list[dict] = []

        def fake_post(url: str, **kw: Any) -> FakeResp:
            calls.append(kw.get("json", {}))
            return FakeResp(
                {
                    "content": [{"type": "text", "text": " uno "}, {"type": "image", "text": ""}, {"type": "text", "text": "dos"}],
                    "usage": {"input_tokens": 4, "output_tokens": 6},
                }
            )

        monkeypatch.setattr(anthropic_mod.httpx, "post", fake_post)
        p = AnthropicProvider()
        assert p.generate("hola") == "uno dos"
        assert calls[0]["model"] == "claude-sonnet-4-20250514"
        assert calls[0]["temperature"] == 0.3

    def test_generate_vacio(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
        monkeypatch.setattr(anthropic_mod.httpx, "post", lambda *a, **k: FakeResp({"content": []}))
        p = AnthropicProvider()
        assert p.generate("hola") == "El modelo no generó ninguna respuesta."

    def test_generate_timeout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
        monkeypatch.setattr(
            anthropic_mod.httpx, "post", lambda *a, **k: (_ for _ in ()).throw(httpx.TimeoutException("t"))
        )
        p = AnthropicProvider()
        assert "tiempo" in p.generate("hola")

    def test_generate_http_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
        monkeypatch.setattr(
            anthropic_mod.httpx,
            "post",
            lambda *a, **k: (_ for _ in ()).throw(
                httpx.HTTPStatusError(
                    "401", request=httpx.Request("POST", "http://fake"), response=httpx.Response(401)
                )
            ),
        )
        p = AnthropicProvider()
        assert "401" in p.generate("hola")

    def test_generate_request_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
        monkeypatch.setattr(anthropic_mod.httpx, "post", lambda *a, **k: (_ for _ in ()).throw(httpx.RequestError("x")))
        p = AnthropicProvider()
        assert "conectar" in p.generate("hola")

    def test_generate_unexpected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
        monkeypatch.setattr(anthropic_mod.httpx, "post", lambda *a, **k: (_ for _ in ()).throw(ValueError("boom")))
        p = AnthropicProvider()
        assert "interno" in p.generate("hola")

    def test_embed_async_degradado(self) -> None:
        import asyncio

        p = AnthropicProvider()
        assert asyncio.run(p.embed_async(["a", "b"])) == [[0.0] * 768, [0.0] * 768]

    def test_health_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
        monkeypatch.setattr(
            anthropic_mod.httpx,
            "get",
            lambda *a, **k: FakeResp({"data": [{"id": "claude-1"}, {"id": "claude-2"}]}),
        )
        p = AnthropicProvider()
        out = p.health()
        assert out["status"] == "ok"
        assert out["modelos_disponibles"] == ["claude-1", "claude-2"]

    def test_health_is_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
        monkeypatch.setattr(anthropic_mod.httpx, "get", lambda *a, **k: FakeResp(status=403, text="denegado"))
        p = AnthropicProvider()
        assert p.health()["status"] == "error"

    def test_health_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
        monkeypatch.setattr(anthropic_mod.httpx, "get", lambda *a, **k: (_ for _ in ()).throw(httpx.RequestError("x")))
        p = AnthropicProvider()
        assert p.health()["status"] == "error"


# ── gemini.py ───────────────────────────────────────────────────────────────


import motor.core.llm.gemini as gemini_mod
from motor.core.llm.gemini import GeminiProvider


class TestGeminiCobertura:
    def test_init_y_urls(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "k")
        p = GeminiProvider()
        assert p._model == "gemini-2.0-flash-001"
        assert p._embedding_model == "text-embedding-004"
        assert "gemini-2.0-flash-001" in p._base_url("gemini-2.0-flash-001")
        assert p._headers()["x-goog-api-key"] == "k"

    def test_generate_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "k")
        calls: list[dict] = []

        def fake_post(url: str, **kw: Any) -> FakeResp:
            calls.append({"url": url, "json": kw.get("json", {})})
            return FakeResp(
                {
                    "candidates": [{"content": {"parts": [{"text": "a"}, {"text": "b"}]}}],
                    "usageMetadata": {"promptTokenCount": 2, "candidatesTokenCount": 3},
                }
            )

        monkeypatch.setattr(gemini_mod.httpx, "post", fake_post)
        p = GeminiProvider()
        assert p.generate("hola") == "ab"
        assert ":generateContent" in calls[0]["url"]
        assert calls[0]["json"]["generationConfig"]["temperature"] == 0.3
        assert calls[0]["json"]["generationConfig"]["maxOutputTokens"] == 1024

    def test_generate_sin_candidates(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "k")
        monkeypatch.setattr(gemini_mod.httpx, "post", lambda *a, **k: FakeResp({}))
        p = GeminiProvider()
        assert p.generate("hola") == "El modelo no generó ninguna respuesta."

    def test_generate_timeout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "k")
        monkeypatch.setattr(
            gemini_mod.httpx, "post", lambda *a, **k: (_ for _ in ()).throw(httpx.TimeoutException("t"))
        )
        p = GeminiProvider()
        assert "tiempo" in p.generate("hola")

    def test_generate_http_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "k")
        monkeypatch.setattr(
            gemini_mod.httpx,
            "post",
            lambda *a, **k: (_ for _ in ()).throw(
                httpx.HTTPStatusError(
                    "429", request=httpx.Request("POST", "http://fake"), response=httpx.Response(429)
                )
            ),
        )
        p = GeminiProvider()
        assert "429" in p.generate("hola")

    def test_generate_request_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "k")
        monkeypatch.setattr(gemini_mod.httpx, "post", lambda *a, **k: (_ for _ in ()).throw(httpx.RequestError("x")))
        p = GeminiProvider()
        assert "conectar" in p.generate("hola")

    def test_generate_unexpected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "k")
        monkeypatch.setattr(gemini_mod.httpx, "post", lambda *a, **k: (_ for _ in ()).throw(ValueError("boom")))
        p = GeminiProvider()
        assert "interno" in p.generate("hola")

    def test_embed_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "k")
        calls: list[dict] = []

        def fake_post(url: str, **kw: Any) -> FakeResp:
            calls.append(kw.get("json", {}))
            return FakeResp({"embeddings": [{"values": [0.1]}, {"values": [0.2]}]})

        monkeypatch.setattr(gemini_mod.httpx, "post", fake_post)
        p = GeminiProvider()
        assert p.embed(["a", "b"]) == [[0.1], [0.2]]
        assert ":batchEmbedContents" in calls[0] if False else len(calls[0]["requests"]) == 2

    def test_embed_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "k")
        monkeypatch.setattr(gemini_mod.httpx, "post", lambda *a, **k: (_ for _ in ()).throw(httpx.RequestError("x")))
        p = GeminiProvider()
        assert p.embed(["a"]) == [[0.0] * 768]

    def test_embed_async_delega(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import asyncio

        monkeypatch.setenv("GEMINI_API_KEY", "k")
        monkeypatch.setattr(
            gemini_mod.httpx,
            "post",
            lambda *a, **k: FakeResp({"embeddings": [{"values": [0.5]}]}),
        )
        p = GeminiProvider()
        assert asyncio.run(p.embed_async(["a"])) == [[0.5]]

    def test_health_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "k")
        monkeypatch.setattr(gemini_mod.httpx, "get", lambda *a, **k: FakeResp({}))
        p = GeminiProvider()
        assert p.health()["status"] == "ok"

    def test_health_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "k")
        monkeypatch.setattr(gemini_mod.httpx, "get", lambda *a, **k: FakeResp(status=400, text="bad"))
        p = GeminiProvider()
        out = p.health()
        assert out["status"] == "error"

    def test_health_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "k")
        monkeypatch.setattr(gemini_mod.httpx, "get", lambda *a, **k: (_ for _ in ()).throw(httpx.RequestError("x")))
        p = GeminiProvider()
        assert p.health()["status"] == "error"


# ── lmstudio.py / vllm.py / openrouter.py (patrón OpenAI-compatible) ───────


import motor.core.llm.lmstudio as lmstudio_mod
import motor.core.llm.openrouter as openrouter_mod
import motor.core.llm.vllm as vllm_mod
from motor.core.llm.lmstudio import LMStudioProvider
from motor.core.llm.openrouter import OpenRouterProvider
from motor.core.llm.vllm import VLLMProvider


def _provider_ok_resp() -> FakeResp:
    return FakeResp(
        {
            "choices": [{"message": {"content": "  rta ok  "}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 2},
        }
    )


class TestLMStudioCobertura:
    def test_generate_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[dict] = []

        def fake_post(url: str, **kw: Any) -> FakeResp:
            calls.append(kw.get("json", {}))
            return _provider_ok_resp()

        monkeypatch.setattr(lmstudio_mod.httpx, "post", fake_post)
        p = LMStudioProvider()
        assert p.generate("hola") == "rta ok"
        assert calls[0]["model"] == "local-model"

    def test_generate_errores(self, monkeypatch: pytest.MonkeyPatch) -> None:
        p = LMStudioProvider()
        for exc, fragmento in [
            (httpx.TimeoutException("t"), "tiempo"),
            (httpx.HTTPStatusError("500", request=httpx.Request("POST", "http://f"), response=httpx.Response(500)), "500"),
            (httpx.RequestError("x"), "conectar"),
            (ValueError("boom"), "interno"),
        ]:
            monkeypatch.setattr(lmstudio_mod.httpx, "post", lambda *a, exc=exc, **k: (_ for _ in ()).throw(exc))
            assert fragmento in p.generate("hola")

    def test_embed_ok_y_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        p = LMStudioProvider()
        monkeypatch.setattr(
            lmstudio_mod.httpx, "post", lambda *a, **k: FakeResp({"data": [{"embedding": [0.3]}, {"embedding": [0.4]}]})
        )
        assert p.embed(["a", "b"]) == [[0.3], [0.4]]
        monkeypatch.setattr(lmstudio_mod.httpx, "post", lambda *a, **k: (_ for _ in ()).throw(httpx.RequestError("x")))
        assert p.embed(["a"]) == [[0.0] * 768]

    def test_embed_async_y_health(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import asyncio

        p = LMStudioProvider()
        monkeypatch.setattr(
            lmstudio_mod.httpx, "post", lambda *a, **k: FakeResp({"data": [{"embedding": [0.9]}]})
        )
        assert asyncio.run(p.embed_async(["a"])) == [[0.9]]
        monkeypatch.setattr(lmstudio_mod.httpx, "get", lambda *a, **k: FakeResp({"data": [{"id": "m1"}]}))
        assert p.health()["status"] == "ok"
        assert p.health()["modelos_disponibles"] == ["m1"]
        monkeypatch.setattr(lmstudio_mod.httpx, "get", lambda *a, **k: FakeResp(status=500, text="e"))
        assert p.health()["status"] == "error"
        monkeypatch.setattr(lmstudio_mod.httpx, "get", lambda *a, **k: (_ for _ in ()).throw(httpx.RequestError("x")))
        assert p.health()["status"] == "error"


class TestVLLMCobertura:
    def test_generate_ok_y_errores(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[dict] = []

        def fake_post(url: str, **kw: Any) -> FakeResp:
            calls.append(kw.get("json", {}))
            return _provider_ok_resp()

        monkeypatch.setattr(vllm_mod.httpx, "post", fake_post)
        p = VLLMProvider()
        assert p.generate("hola") == "rta ok"
        assert calls[0]["model"] == "local-model"
        for exc, fragmento in [
            (httpx.TimeoutException("t"), "tiempo"),
            (httpx.HTTPStatusError("503", request=httpx.Request("POST", "http://f"), response=httpx.Response(503)), "503"),
            (httpx.RequestError("x"), "conectar"),
            (ValueError("boom"), "interno"),
        ]:
            monkeypatch.setattr(vllm_mod.httpx, "post", lambda *a, exc=exc, **k: (_ for _ in ()).throw(exc))
            assert fragmento in p.generate("hola")

    def test_embed_y_health(self, monkeypatch: pytest.MonkeyPatch) -> None:
        p = VLLMProvider()
        monkeypatch.setattr(
            vllm_mod.httpx, "post", lambda *a, **k: FakeResp({"data": [{"embedding": [0.1]}]})
        )
        assert p.embed(["a"]) == [[0.1]]
        monkeypatch.setattr(vllm_mod.httpx, "post", lambda *a, **k: (_ for _ in ()).throw(httpx.RequestError("x")))
        assert p.embed(["a"]) == [[0.0] * 768]
        monkeypatch.setattr(vllm_mod.httpx, "get", lambda *a, **k: FakeResp({"data": [{"id": "v1"}]}))
        assert p.health()["status"] == "ok"
        monkeypatch.setattr(vllm_mod.httpx, "get", lambda *a, **k: FakeResp(status=500))
        assert p.health()["status"] == "error"
        monkeypatch.setattr(vllm_mod.httpx, "get", lambda *a, **k: (_ for _ in ()).throw(httpx.RequestError("x")))
        assert p.health()["status"] == "error"


class TestOpenRouterCobertura:
    def test_init_headers(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENROUTER_API_KEY", "k")
        p = OpenRouterProvider()
        assert p._model == "openrouter/auto"
        assert p._headers()["Authorization"] == "Bearer k"

    def test_generate_ok_y_errores(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENROUTER_API_KEY", "k")
        calls: list[dict] = []

        def fake_post(url: str, **kw: Any) -> FakeResp:
            calls.append(kw.get("json", {}))
            return _provider_ok_resp()

        monkeypatch.setattr(openrouter_mod.httpx, "post", fake_post)
        p = OpenRouterProvider()
        assert p.generate("hola") == "rta ok"
        assert calls[0]["model"] == "openrouter/auto"
        for exc, fragmento in [
            (httpx.TimeoutException("t"), "tiempo"),
            (httpx.HTTPStatusError("402", request=httpx.Request("POST", "http://f"), response=httpx.Response(402)), "402"),
            (httpx.RequestError("x"), "conectar"),
            (ValueError("boom"), "interno"),
        ]:
            monkeypatch.setattr(openrouter_mod.httpx, "post", lambda *a, exc=exc, **k: (_ for _ in ()).throw(exc))
            assert fragmento in p.generate("hola")

    def test_embed_ok_y_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENROUTER_API_KEY", "k")
        p = OpenRouterProvider()
        monkeypatch.setattr(
            openrouter_mod.httpx, "post", lambda *a, **k: FakeResp({"data": [{"embedding": [0.2]}]})
        )
        assert p.embed(["a"]) == [[0.2]]
        monkeypatch.setattr(openrouter_mod.httpx, "post", lambda *a, **k: (_ for _ in ()).throw(httpx.RequestError("x")))
        assert p.embed(["a"]) == [[0.0] * 768]

    def test_health(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENROUTER_API_KEY", "k")
        p = OpenRouterProvider()
        monkeypatch.setattr(openrouter_mod.httpx, "get", lambda *a, **k: FakeResp({"data": [{"id": "o1"}]}))
        assert p.health()["status"] == "ok"
        monkeypatch.setattr(openrouter_mod.httpx, "get", lambda *a, **k: FakeResp(status=500, text="e"))
        assert p.health()["status"] == "error"
        monkeypatch.setattr(openrouter_mod.httpx, "get", lambda *a, **k: (_ for _ in ()).throw(httpx.RequestError("x")))
        assert p.health()["status"] == "error"


# ── ramas pendientes pequeñas ───────────────────────────────────────────────


class TestLlmApiEmbed:
    def test_embed_delega(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import asyncio

        import motor.core.llm as llm_api

        async def fake_embed_async(*a: Any, **k: Any) -> list[list[float]]:
            return [[0.2]]

        fake = SimpleNamespace(
            generate=lambda *a, **k: "ok",
            embed=lambda *a, **k: [[0.1]],
            embed_async=fake_embed_async,
            health=lambda: {"status": "ok"},
        )
        monkeypatch.setattr(llm_api, "_get_state", lambda: fake)
        assert llm_api.embed(["a"]) == [[0.1]]
        assert asyncio.run(llm_api.embed_async(["a"])) == [[0.2]]


class TestMonitorProperties:
    def test_properties(self) -> None:
        import motor.core.llm.monitor as monitor_mod

        m = monitor_mod.PerformanceMonitor()
        assert m.profiler is m._profiler
        assert m.detector is m._detector
        assert m.baseline is m._baseline


class TestRegistryUnregisterDefault:
    def test_unregister_ultimo(self) -> None:
        reg = ProviderRegistry()
        reg.register("a", _MiniProvider(), default=True)
        reg.unregister("a")
        assert reg.default is None
        assert reg.default_name is None


class TestRouterHealthLock:
    def test_espera_cache_vacio(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import threading
        import time

        import motor.core.llm.router.health as hmod

        cache: dict[str, tuple[float, dict[str, Any] | None]] = {"p1": (0.0, None)}
        lock = threading.Lock()
        estado = {"i": 0}

        def fake_sleep(_n: float) -> None:
            estado["i"] += 1
            if estado["i"] == 1:
                cache["p1"] = (time.monotonic(), {"status": "ok"})

        monkeypatch.setattr(hmod.time, "sleep", fake_sleep)
        # Entrada con resultado pendiente (None) -> espera hasta que aparece
        assert hmod.health_get_cached("p1", cache, lock, 10.0) == {"status": "ok"}
        # Entrada fresca cacheada -> devuelve directo
        cache["p1"] = (time.monotonic(), {"status": "ok"})
        assert hmod.health_get_cached("p1", cache, lock, 10.0) == {"status": "ok"}
        # Entrada pendiente que nunca se resuelve -> marca pending y None
        cache["p2"] = (0.0, None)
        assert hmod.health_get_cached("p2", cache, lock, 10.0) is None
        assert cache["p2"] == (0.0, None)
        # Sin entrada -> inicializa pending y None
        assert hmod.health_get_cached("nada", cache, lock, 10.0) is None
        assert cache["nada"] == (0.0, None)
        # Store y remove
        hmod.health_store_cache("p3", {"status": "ok"}, cache, lock)
        assert cache["p3"][1] == {"status": "ok"}
        hmod.health_remove_cache("p3", cache, lock)
        assert "p3" not in cache


class TestRouterBranchProfiler:
    def test_health_con_profiler_y_detector(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import motor.core.llm.router as router_mod
        from motor.core.llm.registry import ProviderRegistry

        class P:
            def health(self) -> dict[str, Any]:
                return {"status": "ok"}

            def generate(self, *a: Any, **k: Any) -> str:
                return "x"

        class Prof:
            def start(self, *a: Any) -> None:
                return None

            def stop(self, *a: Any) -> dict:
                return {"hot": True}

        class Det:
            def evaluate_from_profile(self, *a: Any) -> None:
                return None

        reg = ProviderRegistry()
        reg.register("p", P(), default=True)
        router = router_mod.LLMRouter(registry=reg)
        router._profiler = Prof()
        router._detector = Det()
        out = router.health(provider="p")
        assert out["status"] == "ok"


class TestRamasFinales:
    def test_call_provider_profiler_sin_baseline(self) -> None:
        import motor.core.llm.router.strategy as strat_mod

        class Prof:
            def start(self, *a: Any) -> None:
                return None

            def stop(self, *a: Any) -> Any:
                return SimpleNamespace(wall_time_ms=1.0, cpu_time_ms=0.5, peak_memory_bytes=10)

        class Det:
            def evaluate_from_profile(self, *a: Any) -> None:
                return None

        class CB:
            def call(self, fn: Any) -> Any:
                return fn()

        out = strat_mod._call_provider(
            SimpleNamespace(generate=lambda *a, **k: "rta"),
            "generate",
            "p",
            {},
            monitor=None,
            profiler=Prof(),
            detector=Det(),
            baseline=None,
            provider_name="p",
            task="t",
            model="m",
            cb=CB(),
        )
        assert out == "rta"

    def test_call_provider_con_monitor(self) -> None:
        import motor.core.llm.router.strategy as strat_mod

        class Mon:
            def start_operation(self, *a: Any) -> None:
                return None

            def finish_operation(self, *a: Any) -> None:
                return None

        class CB:
            def call(self, fn: Any) -> Any:
                return fn()

        out = strat_mod._call_provider(
            SimpleNamespace(generate=lambda *a, **k: "m"),
            "generate",
            "p",
            {},
            monitor=Mon(),
            profiler=None,
            detector=None,
            baseline=None,
            provider_name="p",
            task="t",
            model="m",
            cb=CB(),
        )
        assert out == "m"

    def test_call_provider_con_baseline(self) -> None:
        import motor.core.llm.router.strategy as strat_mod

        class Prof:
            def start(self, *a: Any) -> None:
                return None

            def stop(self, *a: Any) -> Any:
                return SimpleNamespace(wall_time_ms=1.0, cpu_time_ms=0.5, peak_memory_bytes=10)

        class Baseline:
            def record(self, *a: Any, **k: Any) -> None:
                return None

        class CB:
            def call(self, fn: Any) -> Any:
                return fn()

        out = strat_mod._call_provider(
            SimpleNamespace(generate=lambda *a, **k: "b"),
            "generate",
            "p",
            {},
            monitor=None,
            profiler=Prof(),
            detector=None,
            baseline=Baseline(),
            provider_name="p",
            task="t",
            model="m",
            cb=CB(),
        )
        assert out == "b"

    def test_openrouter_vllm_embed_async(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import asyncio

        monkeypatch.setenv("OPENROUTER_API_KEY", "k")
        p = OpenRouterProvider()
        monkeypatch.setattr(openrouter_mod.httpx, "post", lambda *a, **k: FakeResp({"data": [{"embedding": [0.1]}]}))
        assert asyncio.run(p.embed_async(["a"])) == [[0.1]]
        p2 = VLLMProvider()
        monkeypatch.setattr(vllm_mod.httpx, "post", lambda *a, **k: FakeResp({"data": [{"embedding": [0.2]}]}))
        assert asyncio.run(p2.embed_async(["a"])) == [[0.2]]

    def test_llm_api_generate_health_via_state(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import motor.core.llm as llm_api

        fake = SimpleNamespace(generate=lambda *a, **k: "g", health=lambda: {"s": "ok"})
        monkeypatch.setattr(llm_api, "_get_state", lambda: fake)
        assert llm_api.generate("p") == "g"
        assert llm_api.health() == {"s": "ok"}


# ── baseline / detector / observability / profiler ──────────────────────────


class TestBaselineCobertura:
    def test_baseline_stats_init(self) -> None:
        import motor.core.llm.baseline as bmod

        b = bmod.BaselineStats()
        assert b.wall_time_p50 == 0.0
        b2 = bmod.BaselineStats(data={"sample_count": 5, "wall_time_p50": 10.0})
        assert b2.sample_count == 5
        assert b2.wall_time_p50 == 10.0
        reg = bmod.RegressionResult("p", "o", "m", 10.0, 20.0, 1.5)
        assert reg.ratio == 2.0
        assert reg.to_dict()["metric"] == "m"
        assert "Regression(" in repr(reg)
        reg0 = bmod.RegressionResult("p", "o", "m", 0.0, 5.0, 1.5)
        assert reg0.ratio == 999.0

    def test_performance_baseline(self, tmp_path: Path) -> None:
        from motor.core.llm.baseline import PerformanceBaseline

        b = PerformanceBaseline()
        for _i in range(5):
            b.record("p", "generate", wall_time_ms=10 + _i, cpu_time_ms=5, peak_memory_bytes=100)
        base = b.get_baseline("p", "generate")
        assert base is not None
        assert base.wall_time_p50 > 0
        cmp = b.compare("p", "generate", wall_time_ms=30, cpu_time_ms=10, peak_memory_bytes=100)
        assert isinstance(cmp, list)
        assert len(b.get_all_baselines()) == 1
        p = tmp_path / "base.json"
        b.save(p)
        b2 = PerformanceBaseline()
        b2.load(p)
        assert b2.get_baseline("p", "generate") is not None
        b.reset()
        assert b.get_baseline("p", "generate") is None


class TestDetectorCobertura:
    def test_hotspot_y_evaluate(self) -> None:
        import motor.core.llm.detector as dmod

        hs = dmod.HotspotRecord(provider="p", operation="o", wall_time_ms=1.0, cpu_time_ms=0.5)
        hs.rank = 3
        d = hs.to_dict()
        assert d["rank"] == 3
        assert "Hotspot(" in repr(hs)
        det = dmod.HotspotDetector(threshold_ms=5.0)
        assert det.threshold_ms == 5.0
        det.threshold_ms = 10.0
        assert det.threshold_ms == 10.0
        rec = det.evaluate(provider="p", operation="o", wall_time_ms=50, cpu_time_ms=5, peak_memory_bytes=1024)
        assert rec is not None
        assert rec.wall_time_ms == 50
        rec2 = det.evaluate(provider="p", operation="o", wall_time_ms=1, cpu_time_ms=1, peak_memory_bytes=1)
        assert rec2 is None
        assert len(det.get_hotspots(n=5, sort_by="memory")) == 1
        assert len(det.get_hotspots(n=5, sort_by="cpu_time")) == 1
        assert len(det.get_hotspots(n=5, sort_by="desconocido")) == 1
        assert det.get_stats()["total_hotspots"] == 1
        assert det.get_stats()["providers"] == ["p"]
        det.reset()
        assert det.get_stats() == {"total_hotspots": 0, "threshold_ms": 10.0}
        assert det.evaluate_from_profile(None) is None
        prof = SimpleNamespace(
            provider="p",
            operation="o",
            wall_time_ms=50,
            cpu_time_ms=5,
            peak_memory_bytes=1024,
            allocations_count=0,
        )
        assert det.evaluate_from_profile(prof) is not None


class TestObservabilityCobertura:
    def test_metrics_ramas(self) -> None:
        import motor.core.llm.observability as obmod

        m = obmod.LLMMetrics()
        m.record("p", "gen", 10.0, success=True, tokens=5)
        m.record("p", "gen", 20.0, success=False, error="timeout")
        m.record("otro", "gen", 1.0, success=True)
        stats = m.get_stats(provider="p")
        assert "p.gen" in stats
        assert stats["p.gen"]["errores"] == {"timeout": 1}
        assert stats["p.gen"]["throughput_qps"] > 0
        assert stats["p.gen"]["tokens_por_segundo"] > 0
        assert "otro.gen" not in stats
        only_op = m.get_stats(operation="gen")
        assert "p.gen" in only_op
        assert m.get_stats(provider="nadie") == {"error": "no data"}
        summ = m.summary()
        assert summ["p"]["fail"] == 1
        assert summ["otro"]["ok"] == 1
        m.reset()
        assert m.get_stats() == {"error": "no data"}


class TestProfilerCobertura:
    def test_profiler_ramas(self) -> None:
        import motor.core.llm.profiler as pmod

        prof = pmod.LLMProfiler(enabled=False)
        assert prof.enabled is False
        assert prof.start("p", "o") is None
        assert prof.stop("p", "o") is None
        prof2 = pmod.LLMProfiler(enabled=True)
        assert prof2.enabled is True
        assert prof2.is_tracing is True
        profile = prof2.start("p", "gen", "m1")
        assert profile is not None
        out = prof2.stop("p", "gen")
        assert out is not None
        assert out.wall_time_ms >= 0
        assert prof2.stop("p", "otra") is None
        d = out.to_dict()
        assert d["allocations"] == 0
        assert "LLMOperationProfile(" in repr(out)
        prof2.stop(provider="p", operation="gen")
        prof2.close() if hasattr(prof2, "close") else None


class TestLlmInitBranch:
    def test_get_state_cacheado(self) -> None:
        import motor.core.llm as llm_api

        prev = llm_api._LLM_STATE
        llm_api._LLM_STATE = SimpleNamespace(generate=lambda *a, **k: "x")
        try:
            assert llm_api._get_state() is llm_api._LLM_STATE
        finally:
            llm_api._LLM_STATE = prev


# ── _state.py: ramas de configuración ───────────────────────────────────────


class TestStateConfigBranches:
    def test_providers_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for nombre in ("openai", "anthropic", "gemini", "openrouter", "lmstudio", "vllm", "groq"):
            cfg = SimpleNamespace(llm_provider=nombre)
            estado = state_mod.build_llm_state(config=cfg)
            assert estado.default_provider is not None
            assert callable(estado.generate)
            assert callable(estado.embed)
            assert callable(estado.health)

    def test_config_default_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        cfg = SimpleNamespace(llm_provider="ollama")
        estado = state_mod.build_llm_state(config=cfg)
        assert estado.default_provider is not None
        assert estado.registry.default_name == "ollama"

    def test_get_optional_providers_import_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        real_import = __import__

        def fake_import(name: str, *a: Any, **k: Any) -> Any:
            if name == "motor.core.llm.openai":
                raise ImportError("boom")
            return real_import(name, *a, **k)

        monkeypatch.setattr("builtins.__import__", fake_import)
        provs = state_mod._get_optional_providers()
        assert all(n != "openai" for _, n in provs)
        assert any(n == "anthropic" for _, n in provs)


class TestStateExceptBranches:
    def test_optional_imports_fail(self, monkeypatch: pytest.MonkeyPatch) -> None:
        real_import = __import__
        rotos = {"anthropic", "gemini", "openrouter", "lmstudio", "vllm", "groq"}

        def fake_import(name: str, *a: Any, **k: Any) -> Any:
            for mod in rotos:
                if name == f"motor.core.llm.{mod}":
                    raise ImportError("boom")
            return real_import(name, *a, **k)

        monkeypatch.setattr("builtins.__import__", fake_import)
        provs = state_mod._get_optional_providers()
        assert all(n == "openai" for _, n in provs)

    def test_registro_provider_falla(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class Boom:
            def __init__(self) -> None:
                raise RuntimeError("no instancia")

        cfg = SimpleNamespace(llm_provider="ollama")
        monkeypatch.setattr(state_mod, "_get_optional_providers", lambda: [(Boom, "boom")])
        estado = state_mod.build_llm_state(config=cfg)
        assert estado.default_provider is not None


# ── base.py ─────────────────────────────────────────────────────────────────


import motor.core.llm.base as base_mod
from motor.core.llm.base import BaseLLMProvider, validate_provider


class _NoBase:
    def generate(self, *a: Any, **k: Any) -> str:
        return "x"


class _SinMetodos(BaseLLMProvider):
    def generate(self, *a: Any, **k: Any) -> str:
        return "x"

    def embed(self, *a: Any, **k: Any) -> list[list[float]]:
        return [[0.0]]

    async def embed_async(self, *a: Any, **k: Any) -> list[list[float]]:
        return [[0.0]]

    def health(self) -> dict[str, Any]:
        return {"status": "ok"}


class TestBaseCobertura:
    def test_supports(self) -> None:
        class P(BaseLLMProvider):
            def generate(self, *a: Any, **k: Any) -> str:
                return "x"

            def embed(self, *a: Any, **k: Any) -> list[list[float]]:
                return [[0.0]]

            async def embed_async(self, *a: Any, **k: Any) -> list[list[float]]:
                return [[0.0]]

            def health(self) -> dict[str, Any]:
                return {"status": "ok"}

        p = P()
        assert p.supports("chat") is True
        assert p.supports("nope") is False
        assert p.supports("max_context") is True

    def test_generate_stream_degradado(self) -> None:
        class P(BaseLLMProvider):
            def generate(self, *a: Any, **k: Any) -> str:
                return "completo"

            def embed(self, *a: Any, **k: Any) -> list[list[float]]:
                return [[0.0]]

            async def embed_async(self, *a: Any, **k: Any) -> list[list[float]]:
                return [[0.0]]

            def health(self) -> dict[str, Any]:
                return {"status": "ok"}

        assert list(P().generate_stream("p")) == ["completo"]

    def test_chat_generate_degradado(self) -> None:
        class P(BaseLLMProvider):
            def generate(self, *a: Any, **k: Any) -> str:
                return "txt"

            def embed(self, *a: Any, **k: Any) -> list[list[float]]:
                return [[0.0]]

            async def embed_async(self, *a: Any, **k: Any) -> list[list[float]]:
                return [[0.0]]

            def health(self) -> dict[str, Any]:
                return {"status": "ok"}

        out = P().chat_generate([{"role": "user", "content": "q"}, {"role": "system", "content": "s"}])
        assert out["content"] == "txt"
        assert out["tool_calls"] is None
        assert out["usage"] == {}

    def test_validation_result_repr(self) -> None:
        r = base_mod.ProviderValidationResult(True, [], "p")
        assert "valid=True" in repr(r)
        r2 = base_mod.ProviderValidationResult(False, ["e1"])
        assert "errors=['e1']" in repr(r2)

    def test_validate_no_heredero(self) -> None:
        res = validate_provider(_NoBase)
        assert not res.valid
        assert any("hereda" in e for e in res.errors)

    def test_validate_no_instanciable(self) -> None:
        class Roto(BaseLLMProvider):
            def __init__(self) -> None:
                raise RuntimeError("no instancia")

            def generate(self, *a: Any, **k: Any) -> str:
                return "x"

            def embed(self, *a: Any, **k: Any) -> list[list[float]]:
                return [[0.0]]

            async def embed_async(self, *a: Any, **k: Any) -> list[list[float]]:
                return [[0.0]]

            def health(self) -> dict[str, Any]:
                return {"status": "ok"}

        res = validate_provider(Roto)
        assert not res.valid
        assert any("instanciar" in e for e in res.errors)

    def test_validate_sin_provider_name(self) -> None:
        class SinNombre(BaseLLMProvider):
            def generate(self, *a: Any, **k: Any) -> str:
                return "x"

            def embed(self, *a: Any, **k: Any) -> list[list[float]]:
                return [[0.0]]

            async def embed_async(self, *a: Any, **k: Any) -> list[list[float]]:
                return [[0.0]]

            def health(self) -> dict[str, Any]:
                return {"status": "ok"}

        res = validate_provider(SinNombre)
        assert not res.valid
        assert any("provider_name" in e for e in res.errors)

    def test_validate_metodo_no_callable(self) -> None:
        class NoCallable(BaseLLMProvider):
            generate = 42  # type: ignore[assignment]
            embed = 42  # type: ignore[assignment]
            embed_async = 42  # type: ignore[assignment]
            health = 42  # type: ignore[assignment]

        res = validate_provider(NoCallable)
        assert not res.valid
        assert any("invocable" in e for e in res.errors)

    def test_validate_firma_incorrecta(self) -> None:
        class MalaFirma(BaseLLMProvider):
            def generate(self, prompt: str) -> str:  # sin model/options
                return "x"

            def embed(self, *a: Any, **k: Any) -> list[list[float]]:
                return [[0.0]]

            async def embed_async(self, *a: Any, **k: Any) -> list[list[float]]:
                return [[0.0]]

            def health(self) -> dict[str, Any]:
                return {"status": "ok"}

        res = validate_provider(MalaFirma)
        assert any("generate" in e for e in res.errors)

    def test_validate_comportamiento_falla(self) -> None:
        class ComportamientoRoto(BaseLLMProvider):
            def generate(self, *a: Any, **k: Any) -> str:
                raise RuntimeError("falla")

            def embed(self, *a: Any, **k: Any) -> list[list[float]]:
                return [[0.0]]

            async def embed_async(self, *a: Any, **k: Any) -> list[list[float]]:
                return [[0.0]]

            def health(self) -> dict[str, Any]:
                return {"status": "ok"}

        res = validate_provider(ComportamientoRoto)
        assert any("generate" in e and "excepción" in e for e in res.errors)

    def test_check_signature_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def mala(*a: Any, **k: Any) -> str:
            return "x"

        def bad_sig(*a: Any, **k: Any) -> Any:
            raise ValueError("no sig")

        monkeypatch.setattr(base_mod.inspect, "signature", bad_sig)
        assert base_mod._check_signature(mala, ["x"], []) is not None


class TestBaseRamasFinales:
    def test_supports_falsy_extra(self) -> None:
        class P(BaseLLMProvider):
            @property
            def capabilities(self) -> dict[str, Any]:
                return {"chat": True, "nada": None, "texto": "hola", "num": 5}

            def generate(self, *a: Any, **k: Any) -> str:
                return "x"

            def embed(self, *a: Any, **k: Any) -> list[list[float]]:
                return [[0.0]]

            async def embed_async(self, *a: Any, **k: Any) -> list[list[float]]:
                return [[0.0]]

            def health(self) -> dict[str, Any]:
                return {"status": "ok"}

        p = P()
        assert p.supports("nada") is False
        assert p.supports("texto") is True
        assert p.supports("num") is True

    def test_validate_falta_metodo(self) -> None:
        class SinMetodos:  # no hereda de BaseLLMProvider
            generate = None
            embed = None
            embed_async = None

        errores: list[str] = []
        base_mod._validar_metodos(SinMetodos(), errores)
        assert any("Falta método" in e for e in errores)

    def test_validate_capacidades_no_dict(self) -> None:
        class CapsRaras(BaseLLMProvider):
            @property
            def capabilities(self) -> dict[str, Any]:
                return "no-dict"  # type: ignore[return-value]

            def generate(self, *a: Any, **k: Any) -> str:
                return "x"

            def embed(self, *a: Any, **k: Any) -> list[list[float]]:
                return [[0.0]]

            async def embed_async(self, *a: Any, **k: Any) -> list[list[float]]:
                return [[0.0]]

            def health(self) -> dict[str, Any]:
                return {"status": "ok"}

        res = validate_provider(CapsRaras)
        assert any("dict" in e for e in res.errors)
        assert any("chat" in e for e in res.errors)

    def test_validate_comportamiento_tipos(self) -> None:
        class TiposRaros(BaseLLMProvider):
            def generate(self, *a: Any, **k: Any) -> str:
                return 42  # type: ignore[return-value]

            def embed(self, *a: Any, **k: Any) -> list[list[float]]:
                return "no-list"  # type: ignore[return-value]

            async def embed_async(self, *a: Any, **k: Any) -> list[list[float]]:
                return [[0.0]]

            def health(self) -> dict[str, Any]:
                return {"status": "ok"}

        res = validate_provider(TiposRaros)
        assert any("str" in e for e in res.errors)
        assert any("list" in e for e in res.errors)

    def test_check_signature_falta_param(self) -> None:
        def fn(prompt: str) -> str:
            return "x"

        def fn2(prompt: str, model: str) -> str:
            return "x"

        def fn3(prompt: str, model: str, options: str) -> str:
            return "x"

        assert base_mod._check_signature(fn3, ["prompt", "model", "options", "otro"], ["options"]) == (
            "falta parámetro 'otro'"
        )
        assert base_mod._check_signature(fn2, ["prompt", "model", "options"], ["options"]) == (
            "falta parámetro 'options'"
        )
        assert base_mod._check_signature(fn, ["prompt", "model"], ["model"]) == "falta parámetro 'model'"
        assert base_mod._check_signature(fn3, ["prompt", "model", "options"], ["options"]) is None

        class ConSelf:
            def metodo(self, prompt: str, model: str, options: str) -> str:
                return "x"

        assert base_mod._check_signature(ConSelf.metodo, ["prompt", "model", "options"], ["options"]) is None
        assert base_mod._check_signature(fn, ["prompt"], []) is None


# ── ramas finales: base, baseline, detector, observability, profiler ────────


class TestRamasFinales2:
    def test_base_embed_firma_incorrecta(self) -> None:
        class EmbedMalo(BaseLLMProvider):
            def generate(self, prompt: str, model: str | None = None, options: dict | None = None) -> str:
                return "x"

            def embed(self, texts: str) -> list[list[float]]:  # firma mala: falta model
                return [[0.0]]

            async def embed_async(self, *a: Any, **k: Any) -> list[list[float]]:
                return [[0.0]]

            def health(self) -> dict[str, Any]:
                return {"status": "ok"}

        res = validate_provider(EmbedMalo)
        assert any("embed" in e for e in res.errors)

    def test_baseline_recompute_vacio(self) -> None:
        from motor.core.llm.baseline import PerformanceBaseline

        b = PerformanceBaseline()
        b._recompute(("p", "o"))
        assert b._baselines.get(("p", "o")) is None

    def test_baseline_compare_insuficiente(self) -> None:
        from motor.core.llm.baseline import PerformanceBaseline

        b = PerformanceBaseline()
        assert b.compare("p", "o", wall_time_ms=5, cpu_time_ms=1, peak_memory_bytes=10) == []
        b.record("p", "o", wall_time_ms=1, cpu_time_ms=1, peak_memory_bytes=10)
        b.record("p", "o", wall_time_ms=1, cpu_time_ms=1, peak_memory_bytes=10)
        assert b.compare("p", "o", wall_time_ms=5, cpu_time_ms=1, peak_memory_bytes=10) == []

    def test_baseline_compare_con_regresion(self) -> None:
        from motor.core.llm.baseline import PerformanceBaseline

        b = PerformanceBaseline()
        for _i in range(5):
            b.record("p", "o", wall_time_ms=1.0, cpu_time_ms=0.5, peak_memory_bytes=100)
        regs = b.compare("p", "o", wall_time_ms=50.0, cpu_time_ms=25.0, peak_memory_bytes=1000)
        assert regs

    def test_baseline_load_inexistente(self, tmp_path: Path) -> None:
        from motor.core.llm.baseline import PerformanceBaseline

        b = PerformanceBaseline()
        b.load(tmp_path / "no_existe.json")
        assert b.get_all_baselines() == {}

    def test_detector_max_records(self) -> None:
        import motor.core.llm.detector as dmod

        det = dmod.HotspotDetector(threshold_ms=1.0, max_records=2)
        for _i in range(5):
            det.evaluate(provider=f"p{_i}", operation="o", wall_time_ms=50, cpu_time_ms=5, peak_memory_bytes=1)
        assert len(det.get_hotspots()) == 2

    def test_observability_max_records(self) -> None:
        import motor.core.llm.observability as obmod

        m = obmod.LLMMetrics()
        for i in range(obmod.MAX_RECORDS + 10):
            m.record("p", "o", float(i), success=True, tokens=1)
        stats = m.get_stats(provider="p")
        assert stats["p.o"]["llamadas_totales"] == obmod.MAX_RECORDS
        assert stats["p.o"]["tokens_medios_por_call"] > 0


class TestRamasFinales3:
    def test_profiler_get_recent_stats_close(self) -> None:
        import motor.core.llm.profiler as pmod

        prof = pmod.LLMProfiler(enabled=True)
        prof.start("p", "gen")
        prof.stop("p", "gen")
        assert len(prof.get_recent(n=5)) == 1
        stats = prof.get_stats(provider="p")
        assert stats["total_operations"] == 1
        assert prof.get_stats(provider="otro") == {}
        prof.close()
        assert prof.enabled is False
        prof.close()  # idempotente

    def test_detector_sort_records(self) -> None:
        import motor.core.llm.detector as dmod

        det = dmod.HotspotDetector(threshold_ms=1.0)
        det.evaluate(provider="a", operation="o", wall_time_ms=10, cpu_time_ms=2, peak_memory_bytes=50)
        det.evaluate(provider="b", operation="o", wall_time_ms=100, cpu_time_ms=5, peak_memory_bytes=500)
        tops = det.get_hotspots(n=1, sort_by="wall_time")
        assert tops[0]["provider"] == "b"
        by_mem = det.get_hotspots(n=1, sort_by="memory")
        assert by_mem[0]["provider"] == "b"

    def test_observability_filtros_operation(self) -> None:
        import motor.core.llm.observability as obmod

        m = obmod.LLMMetrics()
        m.record("p1", "gen", 1.0, success=True)
        m.record("p2", "embed", 2.0, success=True)
        stats = m.get_stats(operation="gen")
        assert "p1.gen" in stats
        assert "p2.embed" not in stats

    def test_registry_unregister_no_default(self) -> None:
        reg = ProviderRegistry()
        reg.register("a", _MiniProvider(), default=True)
        reg.register("b", _MiniProvider())
        reg.unregister("b")
        assert reg.default_name == "a"
        assert "b" not in reg

    def test_router_health_profiler_detector(self) -> None:
        import motor.core.llm.router as router_mod
        from motor.core.llm.registry import ProviderRegistry

        class P:
            def health(self) -> dict[str, Any]:
                return {"status": "ok"}

            def generate(self, *a: Any, **k: Any) -> str:
                return "x"

        class Prof:
            def start(self, *a: Any) -> None:
                return None

            def stop(self, *a: Any) -> Any:
                return {"hot": True}

        class Det:
            def evaluate_from_profile(self, *a: Any) -> None:
                return None

        reg = ProviderRegistry()
        reg.register("p", P(), default=True)
        router = router_mod.LLMRouter(registry=reg)
        router._profiler = Prof()
        router._detector = Det()
        out = router.health(provider="p")
        assert out["status"] == "ok"


class TestRamasFinales4:
    def test_baseline_data_clave_fuera_slots(self) -> None:
        import motor.core.llm.baseline as bmod

        b = bmod.BaselineStats(data={"no_existe": 1, "sample_count": 3})
        assert b.sample_count == 3
        assert not hasattr(b, "no_existe")

    def test_baseline_max_samples(self) -> None:
        from motor.core.llm.baseline import PerformanceBaseline

        b = PerformanceBaseline(max_samples=2)
        for _i in range(5):
            b.record("p", "o", wall_time_ms=float(_i), cpu_time_ms=1.0, peak_memory_bytes=10)
        base = b.get_baseline("p", "o")
        assert base is not None
        assert base.sample_count == 2

    def test_observability_record_sin_error(self) -> None:
        import motor.core.llm.observability as obmod

        m = obmod.LLMMetrics()
        m.record("p", "o", 1.0, success=False)  # sin error
        stats = m.get_stats(provider="p")
        assert stats["p.o"]["errores"] == {}

    def test_router_health_sin_profiler(self) -> None:
        import motor.core.llm.router as router_mod
        from motor.core.llm.registry import ProviderRegistry

        class P:
            def health(self) -> dict[str, Any]:
                return {"status": "ok"}

            def generate(self, *a: Any, **k: Any) -> str:
                return "x"

        reg = ProviderRegistry()
        reg.register("p", P(), default=True)
        router = router_mod.LLMRouter(registry=reg)
        router._profiler = None
        router._detector = None
        router._health_cache.pop("p", None)
        out = router.health(provider="p")
        assert out["status"] == "ok"

    def test_router_health_cached(self) -> None:
        import motor.core.llm.router as router_mod
        from motor.core.llm.registry import ProviderRegistry

        class P:
            def health(self) -> dict[str, Any]:
                return {"status": "ok"}

            def generate(self, *a: Any, **k: Any) -> str:
                return "x"

        reg = ProviderRegistry()
        reg.register("p", P(), default=True)
        router = router_mod.LLMRouter(registry=reg)
        router._health_cache["p"] = (__import__("time").monotonic(), {"status": "cached"})
        assert router.health(provider="p") == {"status": "cached"}


class TestRamasFinales5:
    def test_detector_hotspots_vacio(self) -> None:
        import motor.core.llm.detector as dmod

        det = dmod.HotspotDetector(threshold_ms=1.0)
        assert det.get_hotspots() == []

    def test_router_health_profiler_profile(self) -> None:
        import motor.core.llm.router as router_mod
        from motor.core.llm.registry import ProviderRegistry

        class P:
            def health(self) -> dict[str, Any]:
                return {"status": "ok"}

            def generate(self, *a: Any, **k: Any) -> str:
                return "x"

        llamadas = {"det": 0}

        class Prof:
            def start(self, *a: Any) -> None:
                return None

            def stop(self, *a: Any) -> Any:
                return SimpleNamespace(wall_time_ms=1.0, cpu_time_ms=0.5, peak_memory_bytes=10, allocations_count=0)

        class Det:
            def evaluate_from_profile(self, *a: Any) -> None:
                llamadas["det"] += 1

        reg = ProviderRegistry()
        reg.register("p", P(), default=True)
        router = router_mod.LLMRouter(registry=reg)
        router._health_cache.clear()
        router._profiler = Prof()
        router._detector = Det()
        out = router.health(provider="p")
        assert out["status"] == "ok"
        assert llamadas["det"] == 1


class TestRamasFinales6:
    def test_router_health_profile_falsy(self) -> None:
        import motor.core.llm.router as router_mod
        from motor.core.llm.registry import ProviderRegistry

        class P:
            def health(self) -> dict[str, Any]:
                return {"status": "ok"}

            def generate(self, *a: Any, **k: Any) -> str:
                return "x"

        class Prof:
            def start(self, *a: Any) -> None:
                return None

            def stop(self, *a: Any) -> Any:
                return None  # profile falsy

        class Det:
            def evaluate_from_profile(self, *a: Any) -> None:
                raise AssertionError("no debe llamarse")

        reg = ProviderRegistry()
        reg.register("p", P(), default=True)
        router = router_mod.LLMRouter(registry=reg)
        router._health_cache.clear()
        router._profiler = Prof()
        router._detector = Det()
        out = router.health(provider="p")
        assert out["status"] == "ok"

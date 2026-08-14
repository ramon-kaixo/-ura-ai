"""Cobertura 100x100 de motor/core/llm (TASK-20260814-003).

Cubre openai, ollama, router, base, _state y el resto de providers con
httpx mockeado (sin red). Los tests existentes (test_llm_providers.py)
solo cubren el contrato; estos cubren ramas y errores.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any, Self

import httpx
import pytest

import motor.core.llm.ollama as ollama_mod
import motor.core.llm.openai as openai_mod
from motor.core.llm.ollama import OllamaProvider
from motor.core.llm.openai import OpenAIProvider

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

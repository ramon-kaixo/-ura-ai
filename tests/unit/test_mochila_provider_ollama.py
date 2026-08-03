"""Tests para core/mochila/providers/ollama.py — OllamaProvider."""
from __future__ import annotations

import json
from unittest import mock

import pytest

from core.mochila.providers.base import ProviderError
from core.mochila.providers.ollama import OllamaProvider


class FakeStreamResp:
    def __init__(self, lines: list[str], is_error=False, status_code=200):
        self._lines = lines
        self.is_error = is_error
        self.status_code = status_code

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def aiter_lines(self):
        async def gen():
            for l in self._lines:
                yield l

        return gen()

    async def aread(self):
        return b"error"


class FakePostResp:
    def __init__(self, data: dict, is_error=False, status_code=200, text="err"):
        self._data = data
        self.is_error = is_error
        self.status_code = status_code
        self.text = text

    def json(self):
        return self._data


class FakeGetResp:
    def __init__(self, data: dict, is_error=False, status_code=200, text="err"):
        self._data = data
        self.is_error = is_error
        self.status_code = status_code
        self.text = text
        self.elapsed = mock.Mock()
        self.elapsed.total_seconds.return_value = 0.3

    def json(self):
        return self._data


class FakeClient:
    def __init__(self, stream_resp=None, post_resp=None, get_resp=None):
        self._stream = stream_resp
        self._post = post_resp
        self._get = get_resp

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def stream(self, *a, **k):
        return self._stream

    async def post(self, *a, **k):
        return self._post

    async def get(self, *a, **k):
        return self._get


@pytest.fixture
def provider() -> OllamaProvider:
    return OllamaProvider()


class TestOllamaProvider:
    def test_nombre_timeout(self, provider) -> None:
        assert provider.nombre == "ollama"
        assert provider.timeout == 180

    @pytest.mark.asyncio
    async def test_chat_no_stream_ok(self, provider, monkeypatch) -> None:
        resp = FakePostResp({"id": "c1", "message": {"role": "assistant", "content": "hola"}, "prompt_eval_count": 5, "eval_count": 3})
        client = FakeClient(post_resp=resp)
        monkeypatch.setattr("core.mochila.providers.ollama.httpx.AsyncClient", lambda *a, **k: client)
        out = [d async for d in provider.chat("m1", [])]
        assert out[0]["object"] == "chat.completion"
        assert out[0]["choices"][0]["message"]["content"] == "hola"
        assert out[0]["usage"]["total_tokens"] == 8

    @pytest.mark.asyncio
    async def test_chat_no_stream_error(self, provider, monkeypatch) -> None:
        resp = FakePostResp({}, is_error=True, status_code=500)
        client = FakeClient(post_resp=resp)
        monkeypatch.setattr("core.mochila.providers.ollama.httpx.AsyncClient", lambda *a, **k: client)
        with pytest.raises(ProviderError) as e:
            async for _ in provider.chat("m1", []):
                pass
        assert e.value.status_code == 500

    @pytest.mark.asyncio
    async def test_chat_stream_ok(self, provider, monkeypatch) -> None:
        chunk1 = json.dumps({"id": "x", "message": {"role": "assistant", "content": "hola"}, "done": False})
        chunk2 = json.dumps({"id": "x", "message": {"content": ""}, "done": True})
        stream = FakeStreamResp([chunk1, chunk2])
        client = FakeClient(stream_resp=stream)
        monkeypatch.setattr("core.mochila.providers.ollama.httpx.AsyncClient", lambda *a, **k: client)
        out = [d async for d in provider.chat("m1", [], stream=True)]
        assert len(out) == 2
        assert out[0]["choices"][0]["delta"]["content"] == "hola"
        assert out[1]["choices"][0]["finish_reason"] == "stop"

    @pytest.mark.asyncio
    async def test_chat_stream_error(self, provider, monkeypatch) -> None:
        stream = FakeStreamResp([], is_error=True, status_code=500)
        client = FakeClient(stream_resp=stream)
        monkeypatch.setattr("core.mochila.providers.ollama.httpx.AsyncClient", lambda *a, **k: client)
        with pytest.raises(ProviderError) as e:
            async for _ in provider.chat("m1", [], stream=True):
                pass
        assert e.value.status_code == 500

    @pytest.mark.asyncio
    async def test_health_ok(self, provider, monkeypatch) -> None:
        get = FakeGetResp({"models": [{"name": "m1"}, {"name": "m2"}]})
        client = FakeClient(get_resp=get)
        monkeypatch.setattr("core.mochila.providers.ollama.httpx.AsyncClient", lambda *a, **k: client)
        h = await provider.health()
        assert h["status"] == "ok"
        assert h["modelos_disponibles"] == ["m1", "m2"]

    @pytest.mark.asyncio
    async def test_health_error_http(self, provider, monkeypatch) -> None:
        get = FakeGetResp({}, is_error=True)
        client = FakeClient(get_resp=get)
        monkeypatch.setattr("core.mochila.providers.ollama.httpx.AsyncClient", lambda *a, **k: client)
        h = await provider.health()
        assert h["status"] == "error"

    @pytest.mark.asyncio
    async def test_health_excepcion(self, provider, monkeypatch) -> None:
        class Roto:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def get(self, *a, **k):
                raise OSError("net")

        monkeypatch.setattr("core.mochila.providers.ollama.httpx.AsyncClient", lambda *a, **k: Roto())
        h = await provider.health()
        assert h["status"] == "error"


class TestToOpenAIChunk:
    def test_delta_simple(self) -> None:
        chunk = {"id": "c", "message": {"role": "assistant", "content": "hi"}, "done": False}
        out = OllamaProvider._to_openai_chunk(chunk, "m1")
        assert out["choices"][0]["delta"]["content"] == "hi"
        assert out["choices"][0]["finish_reason"] is None

    def test_delta_tool_calls(self) -> None:
        chunk = {
            "message": {
                "tool_calls": [
                    {"id": "t1", "function": {"name": "web", "arguments": {"q": "x"}}}
                ]
            },
            "done": False,
        }
        out = OllamaProvider._to_openai_chunk(chunk, "m")
        delta = out["choices"][0]["delta"]
        assert "tool_calls" in delta
        assert delta["tool_calls"][0]["function"]["arguments"] == '{"q": "x"}'
        assert out["choices"][0]["finish_reason"] == "tool_calls"

    def test_delta_tool_call_args_str(self) -> None:
        chunk = {"message": {"tool_calls": [{"id": "t1", "function": {"name": "web", "arguments": "{\"q\": \"x\"}"}}]}, "done": True}
        out = OllamaProvider._to_openai_chunk(chunk, "m")
        assert out["choices"][0]["delta"]["tool_calls"][0]["function"]["arguments"] == '{"q": "x"}'
        assert out["choices"][0]["finish_reason"] == "tool_calls"

    def test_content_extrae_tool_call(self) -> None:
        chunk = {"message": {"content": '{"name": "web", "arguments": {"q": "x"}}'}, "done": False}
        out = OllamaProvider._to_openai_chunk(chunk, "m")
        delta = out["choices"][0]["delta"]
        assert delta["tool_calls"][0]["function"]["name"] == "web"
        assert delta["content"] is None

    def test_delta_vacio_no_done(self) -> None:
        chunk = {"message": {"content": ""}, "done": False}
        assert OllamaProvider._to_openai_chunk(chunk, "m") == {}

    def test_done_con_usage(self) -> None:
        chunk = {"message": {"content": ""}, "done": True}
        out = OllamaProvider._to_openai_chunk(chunk, "m")
        assert out["usage"] is not None


class TestExtraerToolCall:
    def test_json_valido(self) -> None:
        out = OllamaProvider._extraer_tool_call('{"name": "web", "arguments": {"q": "x"}}')
        assert out is not None
        assert out[0]["function"]["name"] == "web"
        assert out[0]["function"]["arguments"] == '{"q": "x"}'

    def test_args_dict(self) -> None:
        out = OllamaProvider._extraer_tool_call('{"name": "web", "arguments": {"q": "x"}}')
        assert out[0]["function"]["arguments"] == '{"q": "x"}'

    def test_json_invalido(self) -> None:
        assert OllamaProvider._extraer_tool_call("no es json") is None

    def test_sin_name(self) -> None:
        assert OllamaProvider._extraer_tool_call('{"arguments": {}}') is None

    def test_no_dict(self) -> None:
        assert OllamaProvider._extraer_tool_call("[1,2]") is None


class TestToOpenAI:
    def test_mensaje_simple(self) -> None:
        data = {"id": "c", "message": {"role": "assistant", "content": "resp"}, "prompt_eval_count": 5, "eval_count": 7}
        out = OllamaProvider._to_openai(data, "m1")
        assert out["choices"][0]["message"]["content"] == "resp"
        assert out["choices"][0]["finish_reason"] == "stop"
        assert out["usage"]["total_tokens"] == 12

    def test_con_tool_calls(self) -> None:
        data = {
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"id": "t1", "function": {"name": "web", "arguments": {"q": "x"}}}],
            }
        }
        out = OllamaProvider._to_openai(data, "m")
        msg = out["choices"][0]["message"]
        assert "tool_calls" in msg
        assert out["choices"][0]["finish_reason"] == "tool_calls"

    def test_content_con_tool_call(self) -> None:
        data = {"message": {"role": "assistant", "content": '{"name": "web", "arguments": {"q": "x"}}'}}
        out = OllamaProvider._to_openai(data, "m")
        msg = out["choices"][0]["message"]
        assert msg["content"] == ""
        assert msg["tool_calls"][0]["function"]["name"] == "web"

    def test_usage_defaults(self) -> None:
        out = OllamaProvider._to_openai({"message": {"content": "x"}}, "m")
        assert out["usage"]["total_tokens"] == 0

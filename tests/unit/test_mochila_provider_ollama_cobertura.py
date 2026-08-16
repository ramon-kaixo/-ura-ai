"""Tests de cobertura para core/mochila/providers/ollama.py — OllamaProvider (P2).

Cubre los caminos que el test principal no ejercita: payload con tools,
líneas vacías en stream, extracción de tool call desde el contenido y
respuesta sin contenido (TASK-20260815-003).
"""
from __future__ import annotations

import json

import pytest

from core.mochila.providers.ollama import OllamaProvider


class FakeStreamResp:
    """Respuesta de stream con registro de kwargs."""

    def __init__(self, lines: list[str], is_error: bool = False, status_code: int = 200) -> None:
        self._lines = lines
        self.is_error = is_error
        self.status_code = status_code
        self.kwargs: dict = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a) -> bool:
        return False

    def aiter_lines(self):
        async def gen():
            for line in self._lines:
                yield line

        return gen()

    async def aread(self) -> bytes:
        return b"error"


class FakePostResp:
    """Respuesta POST no-stream con registro de kwargs."""

    def __init__(self, data: dict, is_error: bool = False, status_code: int = 200, text: str = "err") -> None:
        self._data = data
        self.is_error = is_error
        self.status_code = status_code
        self.text = text
        self.kwargs: dict = {}

    def json(self):
        return self._data


class FakeClient:
    """AsyncClient de prueba con captura de kwargs."""

    def __init__(self, stream_resp: FakeStreamResp | None = None, post_resp: FakePostResp | None = None) -> None:
        self._stream = stream_resp
        self._post = post_resp

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a) -> bool:
        return False

    def stream(self, *a, **k):
        assert self._stream is not None
        self._stream.kwargs = k
        return self._stream

    async def post(self, *a, **k):
        assert self._post is not None
        self._post.kwargs = k
        return self._post


@pytest.fixture
def provider() -> OllamaProvider:
    """Proveedor bajo prueba."""
    return OllamaProvider()


class TestChatCobertura:
    """Caminos de chat no cubiertos por el test principal."""

    @pytest.mark.asyncio
    async def test_chat_no_stream_con_tools(self, provider, monkeypatch) -> None:
        """payload incluye tools cuando se pasan (línea 43)."""
        resp = FakePostResp({"id": "c1", "message": {"role": "assistant", "content": "ok"}, "prompt_eval_count": 1, "eval_count": 2})
        client = FakeClient(post_resp=resp)
        monkeypatch.setattr("core.mochila.providers.ollama.httpx.AsyncClient", lambda *a, **k: client)
        tools = [{"type": "function", "function": {"name": "web", "parameters": {}}}]
        out = [d async for d in provider.chat("m1", [], tools=tools)]
        assert out[0]["choices"][0]["message"]["content"] == "ok"
        assert resp.kwargs["json"]["tools"] == tools
        assert resp.kwargs["json"]["options"] == {"num_predict": 4096, "temperature": 0.0}

    @pytest.mark.asyncio
    async def test_chat_stream_con_tools(self, provider, monkeypatch) -> None:
        """stream con tools también incluye el payload tools."""
        chunk = json.dumps({"message": {"content": '{"name": "web", "arguments": {"q": "x"}}'}, "done": False})
        stream = FakeStreamResp([chunk])
        client = FakeClient(stream_resp=stream)
        monkeypatch.setattr("core.mochila.providers.ollama.httpx.AsyncClient", lambda *a, **k: client)
        out = [d async for d in provider.chat("m1", [], stream=True, tools=[{"type": "function"}])]
        assert stream.kwargs["json"]["tools"] == [{"type": "function"}]
        assert out[0]["choices"][0]["delta"]["tool_calls"][0]["function"]["name"] == "web"

    @pytest.mark.asyncio
    async def test_chat_stream_linea_vacia(self, provider, monkeypatch) -> None:
        """las líneas en blanco se ignoran en el stream (rama 61->60)."""
        chunk = json.dumps({"id": "x", "message": {"role": "assistant", "content": "hola"}, "done": False})
        stream = FakeStreamResp(["", "   ", chunk])
        client = FakeClient(stream_resp=stream)
        monkeypatch.setattr("core.mochila.providers.ollama.httpx.AsyncClient", lambda *a, **k: client)
        out = [d async for d in provider.chat("m1", [], stream=True)]
        assert len(out) == 1
        assert out[0]["choices"][0]["delta"]["content"] == "hola"

    @pytest.mark.asyncio
    async def test_chat_stream_json_invalido_linea(self, provider, monkeypatch) -> None:
        """una línea con JSON inválido propaga JSONDecodeError del chunk."""
        stream = FakeStreamResp(["no-es-json"])
        client = FakeClient(stream_resp=stream)
        monkeypatch.setattr("core.mochila.providers.ollama.httpx.AsyncClient", lambda *a, **k: client)
        with pytest.raises(json.JSONDecodeError):
            async for _ in provider.chat("m1", [], stream=True):
                pass


class TestChunkCobertura:
    """Ramas de _to_openai_chunk no cubiertas por el test principal."""

    def test_chunk_vacio_json_objeto(self) -> None:
        """un chunk JSON vacío produce dict vacío y no rompe."""
        out = OllamaProvider._to_openai_chunk(json.loads("{}"), "m")
        assert out == {}

    def test_chunk_uso_final(self) -> None:
        """con done=True se emite usage."""
        chunk = {"message": {"role": "assistant", "content": "fin"}, "done": True}
        out = OllamaProvider._to_openai_chunk(chunk, "m")
        assert out["usage"] == {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        assert out["choices"][0]["finish_reason"] == "stop"


class TestToOpenAICobertura:
    """Ramas de _to_openai no cubiertas por el test principal."""

    def test_contenido_vacio_sin_tool_calls(self) -> None:
        """message sin contenido ni tool_calls (rama 178->183)."""
        data = {"message": {"role": "assistant", "content": ""}}
        out = OllamaProvider._to_openai(data, "m")
        msg = out["choices"][0]["message"]
        assert msg["content"] == ""
        assert out["choices"][0]["finish_reason"] == "stop"

    def test_contenido_no_str(self) -> None:
        """contenido no string se deja tal cual."""
        data = {"message": {"role": "assistant", "content": 42}}
        out = OllamaProvider._to_openai(data, "m")
        assert out["choices"][0]["message"]["content"] == 42

    def test_ids_por_defecto(self) -> None:
        """sin id ni created_at se usan valores por defecto."""
        data = {"message": {"content": "x"}}
        out = OllamaProvider._to_openai(data, "m")
        assert out["id"] == "ollama-unknown"
        assert out["created"] == ""
        assert out["model"] == "m"

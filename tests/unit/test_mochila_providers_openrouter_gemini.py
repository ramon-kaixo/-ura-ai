"""Tests para core/mochila/providers/ — openrouter y gemini."""
from __future__ import annotations

import json
from unittest import mock

import pytest

from core.mochila.providers.base import ProviderError
from core.mochila.providers.gemini import GEMINI_BASE, GeminiProvider, _gemini_api_key
from core.mochila.providers.openrouter import OPENROUTER_BASE, OpenRouterProvider


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
        return b"error body"


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
        self.elapsed.total_seconds.return_value = 0.4

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


class TestGeminiApiKey:
    def test_desde_env(self, monkeypatch) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "env-key")
        assert _gemini_api_key() == "env-key"

    def test_desde_archivo(self, monkeypatch, tmp_path) -> None:
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        cred = tmp_path / "gemini.json"
        cred.parent.mkdir(parents=True, exist_ok=True)
        cred.write_text(json.dumps({"api_key": "file-key"}))
        monkeypatch.setattr("core.mochila.providers.gemini.os.path.expanduser", lambda p: str(cred))
        assert _gemini_api_key() == "file-key"

    def test_archivo_no_existe(self, monkeypatch, tmp_path) -> None:
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.setattr("core.mochila.providers.gemini.os.path.expanduser", lambda p: str(tmp_path / "nope.json"))
        assert _gemini_api_key() == ""

    def test_archivo_corrupto(self, monkeypatch, tmp_path) -> None:
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        cred = tmp_path / "gemini.json"
        cred.parent.mkdir(parents=True, exist_ok=True)
        cred.write_text("no json")
        monkeypatch.setattr("core.mochila.providers.gemini.os.path.expanduser", lambda p: str(cred))
        assert _gemini_api_key() == ""


@pytest.mark.parametrize("provider_cls,key,base", [
    (OpenRouterProvider, "OPENROUTER_API_KEY", OPENROUTER_BASE),
    (GeminiProvider, "GEMINI_API_KEY", GEMINI_BASE),
])
class TestProvidersConKey:
    def test_nombre_timeout(self, provider_cls, key, base, monkeypatch) -> None:
        monkeypatch.setenv(key, "k")
        p = provider_cls()
        assert p.nombre in ("openrouter", "gemini")
        assert p.timeout == 60

    @pytest.mark.asyncio
    async def test_sin_key_chat(self, provider_cls, key, base, monkeypatch) -> None:
        monkeypatch.delenv(key, raising=False)
        monkeypatch.setattr("core.mochila.providers.gemini._gemini_api_key", lambda: "")
        monkeypatch.setattr("core.mochila.providers.openrouter.OpenRouterProvider.__init__", lambda self: setattr(self, "api_key", ""))
        p = provider_cls()
        with pytest.raises(ProviderError, match="no configurada"):
            async for _ in p.chat("m", []):
                pass

    @pytest.mark.asyncio
    async def test_chat_no_stream_ok(self, provider_cls, key, base, monkeypatch) -> None:
        monkeypatch.setenv(key, "k")
        p = provider_cls()
        resp = FakePostResp({"choices": [{"message": {"content": "ok"}}]})
        client = FakeClient(post_resp=resp)
        monkeypatch.setattr("core.mochila.providers.openrouter.httpx.AsyncClient", lambda *a, **k: client)
        monkeypatch.setattr("core.mochila.providers.gemini.httpx.AsyncClient", lambda *a, **k: client)
        out = [d async for d in p.chat("m1", [])]
        assert out[0]["choices"][0]["message"]["content"] == "ok"

    @pytest.mark.asyncio
    async def test_chat_no_stream_error(self, provider_cls, key, base, monkeypatch) -> None:
        monkeypatch.setenv(key, "k")
        p = provider_cls()
        resp = FakePostResp({}, is_error=True, status_code=429)
        client = FakeClient(post_resp=resp)
        monkeypatch.setattr("core.mochila.providers.openrouter.httpx.AsyncClient", lambda *a, **k: client)
        monkeypatch.setattr("core.mochila.providers.gemini.httpx.AsyncClient", lambda *a, **k: client)
        with pytest.raises(ProviderError) as e:
            async for _ in p.chat("m1", []):
                pass
        assert e.value.status_code == 429

    @pytest.mark.asyncio
    async def test_chat_stream_ok(self, provider_cls, key, base, monkeypatch) -> None:
        monkeypatch.setenv(key, "k")
        p = provider_cls()
        chunk = json.dumps({"choices": [{"delta": {"content": "a"}}]})
        stream = FakeStreamResp([f"data: {chunk}", "data: [DONE]"])
        client = FakeClient(stream_resp=stream)
        monkeypatch.setattr("core.mochila.providers.openrouter.httpx.AsyncClient", lambda *a, **k: client)
        monkeypatch.setattr("core.mochila.providers.gemini.httpx.AsyncClient", lambda *a, **k: client)
        out = [d async for d in p.chat("m1", [], stream=True)]
        assert len(out) == 2
        assert out[1]["choices"][0]["finish_reason"] == "stop"

    @pytest.mark.asyncio
    async def test_chat_stream_error(self, provider_cls, key, base, monkeypatch) -> None:
        monkeypatch.setenv(key, "k")
        p = provider_cls()
        stream = FakeStreamResp([], is_error=True, status_code=500)
        client = FakeClient(stream_resp=stream)
        monkeypatch.setattr("core.mochila.providers.openrouter.httpx.AsyncClient", lambda *a, **k: client)
        monkeypatch.setattr("core.mochila.providers.gemini.httpx.AsyncClient", lambda *a, **k: client)
        with pytest.raises(ProviderError) as e:
            async for _ in p.chat("m1", [], stream=True):
                pass
        assert e.value.status_code == 500

    @pytest.mark.asyncio
    async def test_chat_con_tools(self, provider_cls, key, base, monkeypatch) -> None:
        monkeypatch.setenv(key, "k")
        p = provider_cls()
        resp = FakePostResp({"choices": []})
        client = FakeClient(post_resp=resp)
        monkeypatch.setattr("core.mochila.providers.openrouter.httpx.AsyncClient", lambda *a, **k: client)
        monkeypatch.setattr("core.mochila.providers.gemini.httpx.AsyncClient", lambda *a, **k: client)
        out = [d async for d in p.chat("m1", [], tools=[{"t": 1}])]
        assert out == [{"choices": []}]

    @pytest.mark.asyncio
    async def test_health_ok(self, provider_cls, key, base, monkeypatch) -> None:
        monkeypatch.setenv(key, "k")
        p = provider_cls()
        get = FakeGetResp({"data": [{"id": "m1"}]})
        client = FakeClient(get_resp=get)
        monkeypatch.setattr("core.mochila.providers.openrouter.httpx.AsyncClient", lambda *a, **k: client)
        monkeypatch.setattr("core.mochila.providers.gemini.httpx.AsyncClient", lambda *a, **k: client)
        h = await p.health()
        assert h["status"] == "ok"
        assert h["modelos_disponibles"] == ["m1"]

    @pytest.mark.asyncio
    async def test_health_error_http(self, provider_cls, key, base, monkeypatch) -> None:
        monkeypatch.setenv(key, "k")
        p = provider_cls()
        get = FakeGetResp({}, is_error=True)
        client = FakeClient(get_resp=get)
        monkeypatch.setattr("core.mochila.providers.openrouter.httpx.AsyncClient", lambda *a, **k: client)
        monkeypatch.setattr("core.mochila.providers.gemini.httpx.AsyncClient", lambda *a, **k: client)
        h = await p.health()
        assert h["status"] == "error"

    @pytest.mark.asyncio
    async def test_health_excepcion(self, provider_cls, key, base, monkeypatch) -> None:
        monkeypatch.setenv(key, "k")
        p = provider_cls()

        class Roto:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def get(self, *a, **k):
                raise OSError("net")

        monkeypatch.setattr("core.mochila.providers.openrouter.httpx.AsyncClient", lambda *a, **k: Roto())
        monkeypatch.setattr("core.mochila.providers.gemini.httpx.AsyncClient", lambda *a, **k: Roto())
        h = await p.health()
        assert h["status"] == "error"

"""Tests para core/mochila/providers/ — base, deepseek, groq (patrones clonados)."""
from __future__ import annotations

import json
from unittest import mock

import pytest

from core.mochila.providers.base import Provider, ProviderError
from core.mochila.providers.deepseek import DEEPSEEK_BASE, DeepSeekProvider
from core.mochila.providers.groq import GROQ_BASE, GroqProvider


class TestProviderError:
    def test_atributos(self) -> None:
        e = ProviderError("msg", "deepseek", 500)
        assert e.provider == "deepseek"
        assert e.status_code == 500
        assert str(e) == "msg"

    def test_sin_status(self) -> None:
        e = ProviderError("msg", "groq")
        assert e.status_code is None


class TestProviderABC:
    def test_no_instanciable(self) -> None:
        with pytest.raises(TypeError):
            Provider()  # type: ignore[abstract]


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


class FakeClient:
    def __init__(self, stream_resp=None, post_resp=None, get_resp=None):
        self._stream = stream_resp
        self._post = post_resp
        self._get = get_resp
        self.post_calls = 0
        self.stream_calls = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def stream(self, method, url, json=None, headers=None):
        self.stream_calls += 1
        return self._stream

    async def post(self, url, json=None, headers=None):
        self.post_calls += 1
        return self._post

    async def get(self, url, headers=None):
        return self._get


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
        self.elapsed.total_seconds.return_value = 0.5

    def json(self):
        return self._data


@pytest.mark.parametrize("provider_cls,key,base", [
    (DeepSeekProvider, "DEEPSEEK_API_KEY", DEEPSEEK_BASE),
    (GroqProvider, "GROQ_API_KEY", GROQ_BASE),
])
class TestProvidersClonados:
    def test_nombre_timeout(self, provider_cls, key, base, monkeypatch) -> None:
        monkeypatch.setenv(key, "k")
        p = provider_cls()
        assert p.nombre in ("deepseek", "groq")
        assert p.timeout == 60

    @pytest.mark.asyncio
    async def test_sin_api_key_chat(self, provider_cls, key, base, monkeypatch) -> None:
        monkeypatch.delenv(key, raising=False)
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
        monkeypatch.setattr("core.mochila.providers.deepseek.httpx.AsyncClient", lambda *a, **k: client)
        monkeypatch.setattr("core.mochila.providers.groq.httpx.AsyncClient", lambda *a, **k: client)

        out = [d async for d in p.chat("m1", [{"role": "user", "content": "hi"}])]
        assert out[0]["choices"][0]["message"]["content"] == "ok"

    @pytest.mark.asyncio
    async def test_chat_no_stream_error(self, provider_cls, key, base, monkeypatch) -> None:
        monkeypatch.setenv(key, "k")
        p = provider_cls()
        resp = FakePostResp({}, is_error=True, status_code=429)
        client = FakeClient(post_resp=resp)
        monkeypatch.setattr("core.mochila.providers.deepseek.httpx.AsyncClient", lambda *a, **k: client)
        monkeypatch.setattr("core.mochila.providers.groq.httpx.AsyncClient", lambda *a, **k: client)

        with pytest.raises(ProviderError) as e:
            async for _ in p.chat("m1", []):
                pass
        assert e.value.status_code == 429

    @pytest.mark.asyncio
    async def test_chat_stream_ok(self, provider_cls, key, base, monkeypatch) -> None:
        monkeypatch.setenv(key, "k")
        p = provider_cls()
        chunk1 = json.dumps({"choices": [{"delta": {"content": "hola"}}]})
        stream = FakeStreamResp([f"data: {chunk1}", "data: [DONE]"])
        client = FakeClient(stream_resp=stream)
        monkeypatch.setattr("core.mochila.providers.deepseek.httpx.AsyncClient", lambda *a, **k: client)
        monkeypatch.setattr("core.mochila.providers.groq.httpx.AsyncClient", lambda *a, **k: client)

        out = [d async for d in p.chat("m1", [], stream=True)]
        assert len(out) == 2
        assert out[0]["choices"][0]["delta"]["content"] == "hola"
        assert out[1]["choices"][0]["finish_reason"] == "stop"

    @pytest.mark.asyncio
    async def test_chat_stream_error(self, provider_cls, key, base, monkeypatch) -> None:
        monkeypatch.setenv(key, "k")
        p = provider_cls()
        stream = FakeStreamResp([], is_error=True, status_code=500)
        client = FakeClient(stream_resp=stream)
        monkeypatch.setattr("core.mochila.providers.deepseek.httpx.AsyncClient", lambda *a, **k: client)
        monkeypatch.setattr("core.mochila.providers.groq.httpx.AsyncClient", lambda *a, **k: client)

        with pytest.raises(ProviderError) as e:
            async for _ in p.chat("m1", [], stream=True):
                pass
        assert e.value.status_code == 500

    @pytest.mark.asyncio
    async def test_chat_stream_linea_no_data(self, provider_cls, key, base, monkeypatch) -> None:
        monkeypatch.setenv(key, "k")
        p = provider_cls()
        stream = FakeStreamResp(["no-data", "", "data: [DONE]"])
        client = FakeClient(stream_resp=stream)
        monkeypatch.setattr("core.mochila.providers.deepseek.httpx.AsyncClient", lambda *a, **k: client)
        monkeypatch.setattr("core.mochila.providers.groq.httpx.AsyncClient", lambda *a, **k: client)

        out = [d async for d in p.chat("m1", [], stream=True)]
        assert len(out) == 1  # solo el DONE

    @pytest.mark.asyncio
    async def test_chat_con_tools(self, provider_cls, key, base, monkeypatch) -> None:
        monkeypatch.setenv(key, "k")
        p = provider_cls()
        resp = FakePostResp({"choices": []})
        client = FakeClient(post_resp=resp)
        monkeypatch.setattr("core.mochila.providers.deepseek.httpx.AsyncClient", lambda *a, **k: client)
        monkeypatch.setattr("core.mochila.providers.groq.httpx.AsyncClient", lambda *a, **k: client)

        out = [d async for d in p.chat("m1", [], tools=[{"t": 1}])]
        assert out == [{"choices": []}]

    @pytest.mark.asyncio
    async def test_health_sin_key(self, provider_cls, key, base, monkeypatch) -> None:
        monkeypatch.delenv(key, raising=False)
        p = provider_cls()

        h = await p.health()
        assert h["status"] == "no_configurado"

    @pytest.mark.asyncio
    async def test_health_ok(self, provider_cls, key, base, monkeypatch) -> None:
        monkeypatch.setenv(key, "k")
        p = provider_cls()
        get = FakeGetResp({"data": [{"id": "m1"}, {"id": "m2"}]})
        client = FakeClient(get_resp=get)
        monkeypatch.setattr("core.mochila.providers.deepseek.httpx.AsyncClient", lambda *a, **k: client)
        monkeypatch.setattr("core.mochila.providers.groq.httpx.AsyncClient", lambda *a, **k: client)

        h = await p.health()
        assert h["status"] == "ok"
        assert h["modelos_disponibles"] == ["m1", "m2"]
        assert h["total_modelos"] == 2

    @pytest.mark.asyncio
    async def test_health_error_http(self, provider_cls, key, base, monkeypatch) -> None:
        monkeypatch.setenv(key, "k")
        p = provider_cls()
        get = FakeGetResp({}, is_error=True, status_code=500)
        client = FakeClient(get_resp=get)
        monkeypatch.setattr("core.mochila.providers.deepseek.httpx.AsyncClient", lambda *a, **k: client)
        monkeypatch.setattr("core.mochila.providers.groq.httpx.AsyncClient", lambda *a, **k: client)

        h = await p.health()
        assert h["status"] == "error"

    @pytest.mark.asyncio
    async def test_health_excepcion(self, provider_cls, key, base, monkeypatch) -> None:
        monkeypatch.setenv(key, "k")
        p = provider_cls()

        class ClienteRoto:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def get(self, *a, **k):
                raise OSError("net")

        monkeypatch.setattr("core.mochila.providers.deepseek.httpx.AsyncClient", lambda *a, **k: ClienteRoto())
        monkeypatch.setattr("core.mochila.providers.groq.httpx.AsyncClient", lambda *a, **k: ClienteRoto())

        h = await p.health()
        assert h["status"] == "error"

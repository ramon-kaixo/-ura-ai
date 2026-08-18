"""Tests de cobertura real de core/mochila/routes/proxy.py.

Los tests previos (test_mochila_server_cobertura) monkeypatchean los internos;
estos ejercitan el codigo real con mocks de httpx.AsyncClient (sin red).
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Self
from unittest import mock

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.mochila.routes import proxy as proxy_mod


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> dict:
        return self._payload


class FakeStream:
    def __init__(self, lines: list[str]) -> None:
        self._lines = lines

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False

    async def aiter_lines(self):
        for line in self._lines:
            yield line


class FakeAsyncClient:
    """Fake de httpx.AsyncClient: get/post/stream sin red."""

    def __init__(self, responses: dict | None = None, stream_lines: list[str] | None = None) -> None:
        self._responses = responses or {}
        self._stream_lines = stream_lines or []

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False

    async def get(self, *args, **kwargs) -> FakeResponse:
        return FakeResponse(self._responses.get("get", {"ok": "get"}))

    async def post(self, *args, **kwargs) -> FakeResponse:
        return FakeResponse(self._responses.get("post", {"ok": "post"}))

    def stream(self, *args, **kwargs) -> FakeStream:
        return FakeStream(self._stream_lines)


def _state():
    st = mock.Mock()
    st.scheduler = mock.Mock()
    st.scheduler.estimar_vram.return_value = 100
    st.scheduler.acquire = mock.AsyncMock(return_value="req-1")
    st.scheduler.release = mock.AsyncMock()
    return st


def _app(state=None):
    app = FastAPI()
    app.include_router(proxy_mod.create_proxy_router(state or _state()))
    return app


@pytest.fixture(autouse=True)
def _no_httpx(monkeypatch):
    factory = mock.Mock(wraps=lambda *a, **k: FakeAsyncClient())
    factory.__call__ = lambda *a, **k: FakeAsyncClient()  # type: ignore[method-assign]
    monkeypatch.setattr(proxy_mod.httpx, "AsyncClient", lambda *a, **k: FakeAsyncClient())
    yield
    monkeypatch.undo()


def _mock_upstream(monkeypatch, payload: dict, status: int = 200) -> None:
    from fastapi.responses import JSONResponse

    async def _get(request, headers):
        return JSONResponse(content=payload, status_code=status)

    async def _post(request, body, headers):
        return JSONResponse(content=payload, status_code=status)

    monkeypatch.setattr(proxy_mod, "_get_upstream", _get)
    monkeypatch.setattr(proxy_mod, "_post_upstream", _post)


class TestTokenStream:
    def test_response_field(self) -> None:
        assert proxy_mod._token_stream({"response": "hola"}) == "hola"

    def test_message_content(self) -> None:
        assert proxy_mod._token_stream({"message": {"content": "chunk"}}) == "chunk"

    def test_choices_delta(self) -> None:
        assert proxy_mod._token_stream({"choices": [{"delta": {"content": "d"}}]}) == "d"

    def test_vacio(self) -> None:
        assert proxy_mod._token_stream({"nada": 1}) == ""


class TestErrorGuardian:
    def test_con_penalty(self) -> None:
        err = proxy_mod._error_guardian("penalizacion")
        assert err["error"]["message"] == "STREAM_ABORTED_BY_GUARDIAN"
        assert err["error"]["penalty_context"] == "penalizacion"

    def test_sin_penalty(self) -> None:
        err = proxy_mod._error_guardian(None)
        assert "penalty_context" not in err["error"]


class TestLeerBody:
    def test_post_json(self) -> None:
        r = httpx.Request("POST", "http://x/api/chat", json={"model": "m"})
        assert asyncio_run(proxy_mod._leer_body(TestClientRequest(r))) == {"model": "m"}

    def test_get_none(self) -> None:
        r = httpx.Request("GET", "http://x/api/tags")
        assert asyncio_run(proxy_mod._leer_body(TestClientRequest(r))) is None

    def test_json_invalido(self) -> None:
        r = httpx.Request("POST", "http://x/api/chat", content=b"{rotos")
        assert asyncio_run(proxy_mod._leer_body(TestClientRequest(r))) is None


class TestHelpers:
    def test_build_headers_con_auth(self) -> None:
        r = httpx.Request("GET", "http://x/api/tags", headers={"Authorization": "Bearer k"})
        h = proxy_mod._build_headers(TestClientRequest(r))
        assert h["Authorization"] == "Bearer k"

    def test_build_headers_sin_auth(self) -> None:
        r = httpx.Request("GET", "http://x/api/tags")
        assert "Authorization" not in proxy_mod._build_headers(TestClientRequest(r))

    def test_es_opencode_por_modelo(self) -> None:
        assert proxy_mod._es_opencode({"model": "opencode/llama3"}) is True

    def test_es_opencode_por_fuerza(self) -> None:
        assert proxy_mod._es_opencode({"_force_guardian": True}) is True

    def test_es_opencode_falso(self) -> None:
        assert proxy_mod._es_opencode({"model": "llama3"}) is False

    def test_adquirir_vram_path_sin_slash(self) -> None:
        st = _state()
        asyncio_run(proxy_mod._adquirir_vram(st, {"model": "m1"}, "api/chat"))
        st.scheduler.acquire.assert_awaited_once()
        assert st.scheduler.acquire.await_args.kwargs["data"]["model"] == "m1"

    def test_adquirir_vram_path_con_slash(self) -> None:
        st = _state()
        asyncio_run(proxy_mod._adquirir_vram(st, {}, "v1/chat/completions"))
        assert st.scheduler.acquire.await_args.kwargs["data"]["model"] == "v1"

    def test_adquirir_vram_sin_body(self) -> None:
        st = _state()
        asyncio_run(proxy_mod._adquirir_vram(st, None, "tags"))
        assert st.scheduler.acquire.await_args.kwargs["data"]["model"] == "tags"


class TestUpstream:
    def test_get_upstream(self) -> None:
        r = httpx.Request("GET", "http://x/api/tags")
        resp = asyncio_run(proxy_mod._get_upstream(TestClientRequest(r), {"Content-Type": "application/json"}))
        assert resp.status_code == 200
        assert json.loads(resp.body) == {"ok": "get"}

    def test_post_upstream(self) -> None:
        r = httpx.Request("POST", "http://x/api/embed", json={"model": "m"})
        resp = asyncio_run(proxy_mod._post_upstream(TestClientRequest(r), {"model": "m"}, {}))
        assert resp.status_code == 200
        assert json.loads(resp.body) == {"ok": "post"}


class TestProxyGateway:
    def test_get(self, monkeypatch) -> None:
        _mock_upstream(monkeypatch, {"tags": []})
        resp = TestClient(_app()).get("/api/tags")
        assert resp.status_code == 200
        assert resp.json() == {"tags": []}

    def test_post_no_stream(self, monkeypatch) -> None:
        _mock_upstream(monkeypatch, {"embedding": [1]})
        resp = TestClient(_app()).post("/api/embed", json={"model": "m", "stream": False})
        assert resp.status_code == 200
        assert resp.json() == {"embedding": [1]}

    def test_post_stream(self, monkeypatch) -> None:
        monkeypatch.setattr(proxy_mod, "httpx", SimpleNamespace(AsyncClient=lambda *a, **k: FakeAsyncClient(stream_lines=['{"response":"hola"}'])))
        resp = TestClient(_app()).post("/api/chat", json={"model": "llama3", "stream": True})
        assert resp.status_code == 200
        assert b'"hola"' in resp.content

    def test_vram_denied(self) -> None:
        st = _state()
        st.scheduler.acquire.return_value = None
        resp = TestClient(_app(st)).post("/api/chat", json={"model": "m", "stream": True})
        assert resp.status_code == 503

    def test_connect_error(self, monkeypatch) -> None:
        async def _boom(request, body, headers):
            raise httpx.ConnectError("sin ollama")

        monkeypatch.setattr(proxy_mod, "_post_upstream", _boom)
        resp = TestClient(_app()).post("/api/embed", json={"model": "m", "stream": False})
        assert resp.status_code == 502


class TestProxyStream:
    def test_linea_vacia(self, monkeypatch) -> None:
        out = run_stream([""])
        assert out == ["\n"]

    def test_guardian_none(self, monkeypatch) -> None:
        out = run_stream(['{"response":"a"}', '{"response":"b"}'])
        assert out == ['{"response":"a"}\n', '{"response":"b"}\n']

    def test_guardian_pasa(self, monkeypatch) -> None:
        g = mock.Mock()
        g.evaluar_texto_stream.return_value = True
        out = run_stream(['{"response":"ok"}'], is_opencode=True, guardian=g)
        assert out == ['{"response":"ok"}\n']
        g.evaluar_texto_stream.assert_called_once_with("ok")

    def test_guardian_aborta(self, monkeypatch) -> None:
        g = mock.Mock()
        g.evaluar_texto_stream.return_value = False
        g.generar_penalizacion.return_value = "p1"
        monkeypatch.setattr(proxy_mod, "log_event", mock.Mock())
        out = run_stream(['{"response":"mal"}', '{"response":"x"}'], is_opencode=True, guardian=g)
        assert len(out) == 1
        assert "STREAM_ABORTED_BY_GUARDIAN" in out[0]
        assert "p1" in out[0]

    def test_chunk_no_json(self, monkeypatch) -> None:
        out = run_stream(["no-json", '{"response":"a"}'])
        assert out == ["no-json\n", '{"response":"a"}\n']

    def test_chunk_no_json_opencode(self, monkeypatch) -> None:
        g = mock.Mock()
        g.evaluar_texto_stream.return_value = True
        out = run_stream(["no-json", '{"response":"a"}'], is_opencode=True, guardian=g)
        assert out == ["no-json\n", '{"response":"a"}\n']
        g.evaluar_texto_stream.assert_called_once_with("a")


def run_stream(lines: list[str], is_opencode: bool = False, guardian=None) -> list[str]:
    client = FakeAsyncClient(stream_lines=lines)
    with mock.patch.object(proxy_mod.httpx, "AsyncClient", lambda *a, **k: client):
        r = httpx.Request("POST", "http://x/api/chat", json={"model": "m", "stream": True})
        body = {"model": "m", "stream": True}
        gen = proxy_mod._proxy_stream(TestClientRequest(r), body, {}, is_opencode, guardian, "api/chat")
        return list(asyncio_run(agen_to_list(gen)))


async def agen_to_list(agen):
    return [item async for item in agen]


class TestClientRequest:
    """Wrapper minimo: Request de httpx no es Request de Starlette."""

    def __init__(self, httpx_request: httpx.Request) -> None:
        self._req = httpx_request

    @property
    def method(self) -> str:
        return self._req.method

    @property
    def url(self):
        return self._req.url

    @property
    def headers(self):
        return self._req.headers

    @property
    def query_params(self):
        return self._req.url.params

    async def json(self):
        try:
            return json.loads(self._req.content) if self._req.content else None
        except Exception:
            raise ValueError("invalid json") from None


def asyncio_run(coro):
    import asyncio

    return asyncio.run(coro)

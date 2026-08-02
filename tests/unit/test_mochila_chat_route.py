"""Tests para core/mochila/routes/chat.py — /v1/chat/completions."""
from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

import pytest

from core.mochila._state import MochilaState


def _state() -> MochilaState:
    st = MochilaState(providers={}, provider_timeouts={})
    st.router = mock.Mock()
    st.router.route.return_value = SimpleNamespace(provider="ollama", modelo="m1", route_reason="codigo")
    st.circuit_breaker = mock.Mock()
    st.circuit_breaker.puede_pasar.return_value = True
    st.circuit_breaker.estado.return_value = {"state": "CLOSED"}
    st.rate_limiter = mock.Mock()
    st.rate_limiter.puede_pasar.return_value = (True, 0, 100)
    st.cost_tracker = mock.Mock()
    return st


def _provider_chat(return_chunk: dict):
    provider = mock.Mock()

    def _chat(**kwargs):
        async def _inner():
            yield return_chunk

        return _inner()

    provider.chat = _chat
    return provider


class TestRechazarSiBloqueado:
    def test_circuit_open(self) -> None:
        from fastapi import HTTPException

        from core.mochila.routes.chat import _rechazar_si_bloqueado

        cb = mock.Mock()
        cb.puede_pasar.return_value = False
        cb.estado.return_value = {"state": "OPEN"}
        with pytest.raises(HTTPException) as e:
            _rechazar_si_bloqueado("ollama", cb, mock.Mock())
        assert e.value.status_code == 503

    def test_rate_limit(self) -> None:
        from fastapi import HTTPException

        from core.mochila.routes.chat import _rechazar_si_bloqueado

        cb = mock.Mock()
        cb.puede_pasar.return_value = True
        rl = mock.Mock()
        rl.puede_pasar.return_value = (False, 10, 5)
        with pytest.raises(HTTPException) as e:
            _rechazar_si_bloqueado("ollama", cb, rl)
        assert e.value.status_code == 429

    def test_ok_no_raise(self) -> None:
        from core.mochila.routes.chat import _rechazar_si_bloqueado

        cb = mock.Mock()
        cb.puede_pasar.return_value = True
        rl = mock.Mock()
        rl.puede_pasar.return_value = (True, 0, 100)
        _rechazar_si_bloqueado("ollama", cb, rl)  # no debe lanzar


class TestChatNoStream:
    @pytest.mark.asyncio
    async def test_retorna_chunk(self) -> None:
        from core.mochila.routes.chat import _chat_no_stream

        provider = _provider_chat({"choices": [{"message": {"content": "hola"}}]})
        out = await _chat_no_stream(provider, "m1", [], None, 100, 0.0)
        assert out["choices"][0]["message"]["content"] == "hola"

    @pytest.mark.asyncio
    async def test_error_provider(self) -> None:
        from fastapi import HTTPException

        from core.mochila.routes.chat import _chat_no_stream

        provider = mock.Mock()

        def _chat(**kwargs):
            async def _inner():
                raise RuntimeError("fallo")

            return _inner()

        provider.chat = _chat
        with pytest.raises(HTTPException) as e:
            await _chat_no_stream(provider, "m1", [], None, 100, 0.0)
        assert e.value.status_code == 502

    @pytest.mark.asyncio
    async def test_generador_vacio(self) -> None:
        from core.mochila.routes.chat import _chat_no_stream

        provider = mock.Mock()

        def _chat(**kwargs):
            async def _inner():
                return
                yield  # pragma: no cover

            return _inner()

        provider.chat = _chat
        assert await _chat_no_stream(provider, "m1", [], None, 100, 0.0) is None


class TestChatRouter:
    def _app(self, state: MochilaState):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from core.mochila.routes.chat import create_chat_router

        app = FastAPI()
        app.include_router(create_chat_router(state))
        return TestClient(app)

    def test_chat_basico(self) -> None:
        st = _state()
        st.providers["ollama"] = _provider_chat({"choices": [{"message": {"content": "respuesta"}}]})
        client = self._app(st)
        r = client.post("/v1/chat/completions", json={"model": "m1", "messages": [{"role": "user", "content": "hola"}]})
        assert r.status_code == 200
        assert r.headers["X-Mochila-Provider"] == "ollama"
        assert r.json()["choices"][0]["message"]["content"] == "respuesta"
        st.circuit_breaker.registrar_exito.assert_called_once_with("ollama")
        st.rate_limiter.registrar.assert_called_once_with("ollama")

    def test_no_provider_available(self) -> None:
        from core.mochila.router import NoProviderAvailable

        st = _state()
        st.router.route.side_effect = NoProviderAvailable("sin proveedores")
        client = self._app(st)
        r = client.post("/v1/chat/completions", json={"model": "m1", "messages": [{"role": "user", "content": "x"}]})
        assert r.status_code == 503

    def test_circuit_breaker_bloquea(self) -> None:
        st = _state()
        st.circuit_breaker.puede_pasar.return_value = False
        st.circuit_breaker.estado.return_value = {"state": "OPEN"}
        client = self._app(st)
        r = client.post("/v1/chat/completions", json={"model": "m1", "messages": [{"role": "user", "content": "x"}]})
        assert r.status_code == 503

    def test_rate_limit_bloquea(self) -> None:
        st = _state()
        st.rate_limiter.puede_pasar.return_value = (False, 10, 5)
        client = self._app(st)
        r = client.post("/v1/chat/completions", json={"model": "m1", "messages": [{"role": "user", "content": "x"}]})
        assert r.status_code == 429

    def test_respuesta_vacia_502(self) -> None:
        st = _state()
        st.providers["ollama"] = mock.Mock()
        st.providers["ollama"].chat = mock.Mock()
        client = self._app(st)
        r = client.post("/v1/chat/completions", json={"model": "m1", "messages": [{"role": "user", "content": "x"}]})
        assert r.status_code == 502

    def test_stream(self) -> None:
        st = _state()
        st.providers["ollama"] = _provider_chat({"choices": [{"delta": {"content": "a"}, "index": 0}]})
        client = self._app(st)
        r = client.post("/v1/chat/completions", json={"model": "m1", "messages": [{"role": "user", "content": "x"}], "stream": True})
        assert r.status_code == 200
        assert "text/event-stream" in r.headers["content-type"]
        assert "X-Mochila-Provider" in r.headers

    def test_stream_con_tools_true(self) -> None:
        st = _state()
        st.providers["ollama"] = _provider_chat({"choices": [{"delta": {"content": "b"}, "index": 0}]})
        with mock.patch("core.mochila.routes.chat.TOOL_SCHEMAS", [{"tipo": "web"}]):
            client = self._app(st)
            r = client.post("/v1/chat/completions", json={"model": "m1", "messages": [{"role": "user", "content": "x"}], "stream": True, "tools": True})
        assert r.status_code == 200

    def test_tool_calls_ejecuta(self) -> None:
        st = _state()
        msg = {
            "choices": [
                {
                    "message": {
                        "content": "",
                        "tool_calls": [
                            {"id": "c1", "function": {"name": "web_search", "arguments": "{\"q\": \"test\"}"}}
                        ],
                    }
                }
            ]
        }
        st.providers["ollama"] = _provider_chat(msg)
        with mock.patch("core.mochila.routes.chat.ejecutar_tool", mock.AsyncMock(return_value={"result": "ok"})) as tool:
            client = self._app(st)
            r = client.post("/v1/chat/completions", json={"model": "m1", "messages": [{"role": "user", "content": "x"}]})
        assert r.status_code == 200
        tool.assert_awaited_once_with("web_search", {"q": "test"})

    def test_force_guardian(self) -> None:
        st = _state()
        st.providers["ollama"] = _provider_chat({"choices": [{"message": {"content": "con guardian"}}]})
        with mock.patch("core.mochila.routes.chat.OpenCodeGuardian") as Guardian:
            Guardian.return_value = mock.Mock()
            client = self._app(st)
            r = client.post(
                "/v1/chat/completions",
                json={"model": "m1", "messages": [{"role": "user", "content": "x"}], "force_guardian": True},
            )
        assert r.status_code == 200

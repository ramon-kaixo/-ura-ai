"""Tests para core/auth_layer.py y core/mochila/streaming.py."""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest import mock

import pytest

import core.auth_layer as auth
from core.mochila._state import MochilaState
from core.mochila.streaming import _stream_from_provider


class TestAuthLayer:
    @pytest.fixture(autouse=True)
    def auth_on(self, monkeypatch):
        monkeypatch.setattr(auth, "AUTH_ENABLED", True)
        yield
        monkeypatch.setattr(auth, "AUTH_ENABLED", True)

    def test_auth_deshabilitado(self, monkeypatch) -> None:
        monkeypatch.setattr(auth, "AUTH_ENABLED", False)
        assert auth.validate(None) is True
        assert auth.require_auth() is False

    def test_sin_api_key_false(self) -> None:
        assert auth.validate(None) is False
        assert auth.validate("") is False

    def test_key_correcta_con_store(self, monkeypatch) -> None:
        store = mock.Mock()
        store.get_secret.return_value = "secreto"
        assert auth.validate("secreto", store) is True

    def test_key_incorrecta(self, monkeypatch) -> None:
        store = mock.Mock()
        store.get_secret.return_value = "secreto"
        assert auth.validate("otra", store) is False

    def test_get_api_key_store_sin_key_fallback(self, monkeypatch) -> None:
        store = mock.Mock()
        store.get_secret.return_value = None
        getter = mock.Mock(return_value="env_key")
        monkeypatch.setattr("motor.core.secrets.get_secret", getter)
        assert auth._get_api_key(store) == "env_key"

    def test_get_api_key_error(self, monkeypatch) -> None:
        store = mock.Mock()
        store.get_secret.return_value = None
        monkeypatch.setattr("motor.core.secrets.get_secret", mock.Mock(return_value=None))
        with pytest.raises(RuntimeError, match="URA_API_KEY not configured"):
            auth._get_api_key(store)


class TestStreamFromProvider:
    def _state(self) -> MochilaState:
        state = MochilaState(providers={}, provider_timeouts={})
        state.circuit_breaker = mock.Mock()
        state.rate_limiter = mock.Mock()
        state.cost_tracker = mock.Mock()
        return state

    @pytest.mark.asyncio
    async def test_flujo_normal(self) -> None:
        state = self._state()
        state.providers["ollama"] = SimpleNamespace()
        state.provider_timeouts["ollama"] = 60.0

        async def fake_chat(**kwargs):
            yield {"choices": [{"delta": {"content": "hola"}, "index": 0}]}
            yield {"choices": [{"delta": {}, "finish_reason": "stop", "index": 0}]}

        state.providers["ollama"].chat = fake_chat
        out = b"".join([c async for c in _stream_from_provider("ollama", "m1", [], None, 100, 0.0, state)])
        assert b"hola" in out
        assert b"[DONE]" in out
        state.circuit_breaker.registrar_exito.assert_called()
        state.rate_limiter.registrar.assert_called()

    @pytest.mark.asyncio
    async def test_chunk_vacio_se_omite(self) -> None:
        state = self._state()
        state.providers["ollama"] = SimpleNamespace()
        state.provider_timeouts["ollama"] = 60.0

        async def fake_chat(**kwargs):
            yield None
            yield {}
            yield {"choices": [{"delta": {}, "finish_reason": "stop", "index": 0}]}

        state.providers["ollama"].chat = fake_chat
        out = b"".join([c async for c in _stream_from_provider("ollama", "m1", [], None, 100, 0.0, state)])
        assert b"[DONE]" in out

    @pytest.mark.asyncio
    async def test_timeout_error(self) -> None:
        state = self._state()
        state.providers["ollama"] = SimpleNamespace()
        state.provider_timeouts["ollama"] = 60.0

        async def _inner():
            raise TimeoutError("tarde")
            yield  # pragma: no cover

        def fake_chat(**kwargs):
            return _inner()

        state.providers["ollama"].chat = fake_chat
        out = b"".join([c async for c in _stream_from_provider("ollama", "m1", [], None, 100, 0.0, state)])
        assert b"timeout_error" in out
        state.circuit_breaker.registrar_fallo.assert_called_once_with("ollama", es_timeout=True)

    @pytest.mark.asyncio
    async def test_error_generico(self) -> None:
        state = self._state()
        state.providers["ollama"] = SimpleNamespace()
        state.provider_timeouts["ollama"] = 60.0

        async def _inner():
            raise RuntimeError("fallo")
            yield  # pragma: no cover

        def fake_chat(**kwargs):
            return _inner()

        state.providers["ollama"].chat = fake_chat
        out = b"".join([c async for c in _stream_from_provider("ollama", "m1", [], None, 100, 0.0, state)])
        assert b"provider_error" in out
        state.circuit_breaker.registrar_fallo.assert_called_once_with("ollama")

    @pytest.mark.asyncio
    async def test_guardian_aborta(self) -> None:
        state = self._state()
        state.providers["ollama"] = SimpleNamespace()
        state.provider_timeouts["ollama"] = 60.0
        guardian = mock.Mock()
        guardian.evaluar_texto_stream.return_value = False
        guardian.generar_penalizacion.return_value = "pena"

        async def fake_chat(**kwargs):
            yield {"choices": [{"delta": {"content": "texto peligroso"}, "index": 0}]}
            yield {"choices": [{"delta": {}, "finish_reason": "stop", "index": 0}]}

        state.providers["ollama"].chat = fake_chat
        out = b"".join([c async for c in _stream_from_provider("ollama", "m1", [], None, 100, 0.0, state, is_opencode=True, guardian=guardian)])
        assert b"STREAM_ABORTED_BY_GUARDIAN" in out
        assert b"pena" in out
        guardian.evaluar_texto_stream.assert_called_once()

    @pytest.mark.asyncio
    async def test_guardian_aprueba(self) -> None:
        state = self._state()
        state.providers["ollama"] = SimpleNamespace()
        state.provider_timeouts["ollama"] = 60.0
        guardian = mock.Mock()
        guardian.evaluar_texto_stream.return_value = True

        async def fake_chat(**kwargs):
            yield {"choices": [{"delta": {"content": "bien"}, "index": 0}]}
            yield {"choices": [{"delta": {}, "finish_reason": "stop", "index": 0}]}

        state.providers["ollama"].chat = fake_chat
        out = b"".join([c async for c in _stream_from_provider("ollama", "m1", [], None, 100, 0.0, state, is_opencode=True, guardian=guardian)])
        assert b"bien" in out
        assert b"STREAM_ABORTED" not in out

    @pytest.mark.asyncio
    async def test_flujo_sin_finish_reason(self) -> None:
        state = self._state()
        state.providers["ollama"] = SimpleNamespace()
        state.provider_timeouts["ollama"] = 60.0

        async def fake_chat(**kwargs):
            yield {"choices": [{"delta": {"content": "x"}, "index": 0}]}
            return

        state.providers["ollama"].chat = fake_chat
        out = b"".join([c async for c in _stream_from_provider("ollama", "m1", [], None, 100, 0.0, state)])
        assert b"[DONE]" in out

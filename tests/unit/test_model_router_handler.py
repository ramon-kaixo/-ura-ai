"""Tests de core/model_router/handler.py (TASK-20260812-022).

Cubre los métodos del RouterHandler con dobles: _get_modelos (cache),
_send_json, _check_rate_limit (rate_limiter global) y do_GET (dispatch).
"""

import io
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.model_router import model_selection as ms
from core.model_router.handler import RouterHandler


@pytest.fixture(autouse=True)
def _limpiar_cache_router():
    """Limpia el estado de CLASE compartido antes y después de cada test.

    IMPORTANTE (TASK-20260812-022): RouterHandler._modelos_cache es un
    atributo de CLASE. Los tests usan _FakeHandler (subclase), cuyo cache es
    SEPARADO del padre tras el primer seteo. Hay que limpiar AMBAS clases:
    la subclase (la que usa el classmethod con cls=_FakeHandler) y el padre.
    """
    for cls in (RouterHandler, _FakeHandler):
        cls._modelos_cache = None
        cls._cache_ts = 0
    yield
    for cls in (RouterHandler, _FakeHandler):
        cls._modelos_cache = None
        cls._cache_ts = 0


class _FakeHandler(RouterHandler):
    """Handler con sockets falsos para testear sin servidor."""

    def __init__(self) -> None:
        self.wfile = io.BytesIO()
        self.rfile = io.BytesIO()
        self.headers = MagicMock()
        self.path = "/"
        self.command = "GET"
        self.server = MagicMock()
        self.server.server_address = ("127.0.0.1", 11435)
        self.client_address = ("127.0.0.1", 12345)
        self.send_response = MagicMock()
        self.send_header = MagicMock()
        self.end_headers = MagicMock()
        self._rate_limiter = MagicMock()
        self._rate_limiter.check.return_value = True


def _make_handler() -> _FakeHandler:
    return _FakeHandler()


def _reset_cache(monkeypatch) -> None:
    monkeypatch.setattr(RouterHandler, "_modelos_cache", None)
    monkeypatch.setattr(RouterHandler, "_cache_ts", 0)


def test_get_modelos_cache_fresco(monkeypatch) -> None:
    h = _make_handler()
    _reset_cache(monkeypatch)
    _FakeHandler._modelos_cache = {"modelo1"}
    _FakeHandler._cache_ts = time.time()
    llamadas: list[int] = []

    def fake():
        llamadas.append(1)
        return {"modelo_x"}

    with patch.object(ms, "obtener_modelos_disponibles", fake):
        assert "modelo1" in h._get_modelos()
    assert llamadas == []


def test_get_modelos_cache_expirado(monkeypatch) -> None:
    h = _make_handler()
    _reset_cache(monkeypatch)
    _FakeHandler._modelos_cache = {"viejo"}
    _FakeHandler._cache_ts = time.time() - 400
    llamadas: list[int] = []

    def fake():
        llamadas.append(1)
        return {"nuevo"}

    with patch.object(ms, "obtener_modelos_disponibles", fake):
        assert "nuevo" in h._get_modelos()
    assert llamadas == [1]


def test_get_modelos_sin_cache(monkeypatch) -> None:
    h = _make_handler()
    _reset_cache(monkeypatch)
    llamadas: list[int] = []

    def fake():
        llamadas.append(1)
        return {"inicial"}

    with patch.object(ms, "obtener_modelos_disponibles", fake):
        assert "inicial" in h._get_modelos()
    assert llamadas == [1]


class TestSendJson(unittest.TestCase):
    def test_envia_json(self) -> None:
        h = _make_handler()
        h._send_json({"ok": True}, status=200)
        h.send_response.assert_called_once_with(200)
        h.send_header.assert_any_call("Content-Type", "application/json")
        payload = h.wfile.getvalue().decode()
        self.assertIn('"ok"', payload)

    def test_envia_con_status_429(self) -> None:
        h = _make_handler()
        h._send_json({"error": "limit"}, status=429)
        h.send_response.assert_called_once_with(429)


class TestCheckRateLimit(unittest.TestCase):
    def test_rate_limit_ok(self) -> None:
        h = _make_handler()
        with patch("core.model_router.router.rate_limiter") as mock_rl:
            mock_rl.is_allowed.return_value = True
            self.assertTrue(h._check_rate_limit())

    def test_rate_limit_bloquea(self) -> None:
        h = _make_handler()
        with patch("core.model_router.router.rate_limiter") as mock_rl:
            mock_rl.is_allowed.return_value = False
            with patch.object(h, "_send_json") as mock_send:
                self.assertFalse(h._check_rate_limit())
                mock_send.assert_called_once()
                self.assertEqual(mock_send.call_args.args[1], 429)


class TestDoGet(unittest.TestCase):
    def setUp(self) -> None:
        self.h = _make_handler()
        self.h._check_rate_limit = MagicMock(return_value=True)  # type: ignore[method-assign]

    def test_api_tags(self) -> None:
        self.h.path = "/api/tags"
        with patch.object(self.h, "_handle_api_tags") as mock:
            self.h.do_GET()
        mock.assert_called_once()

    def test_health(self) -> None:
        self.h.path = "/health"
        with patch.object(self.h, "_handle_health") as mock:
            self.h.do_GET()
        mock.assert_called_once()

    def test_metrics(self) -> None:
        self.h.path = "/metrics"
        with patch.object(self.h, "_handle_metrics") as mock:
            self.h.do_GET()
        mock.assert_called_once()

    def test_rate_limit_primero(self) -> None:
        self.h._check_rate_limit = MagicMock(return_value=False)  # type: ignore[method-assign]
        self.h.path = "/api/tags"
        with patch.object(self.h, "_handle_api_tags") as mock:
            self.h.do_GET()
        mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()

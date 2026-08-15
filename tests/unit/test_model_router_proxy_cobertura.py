"""Cobertura 100x100 de core/model_router/proxy.py (TASK-20260815-003).

Cubre los wrappers VRAM asíncronos (_proxy_con_guardia_vram,
_proxy_request_async, _proxy_con_vram en sus dos vías: sin loop activo y con
loop activo vía ThreadPoolExecutor) y las ramas de proxy_request que el
archivo de tests original no ejercita (except handlers sin modelo/tipo y
excepción genérica con modelo/tipo). Sin red real ni efectos laterales.
"""

from __future__ import annotations

import asyncio
import json
import urllib.error
from unittest.mock import AsyncMock, patch

from core.model_router import proxy


class TestProxyRequestAsync:
    """_proxy_request_async delega en proxy_request vía to_thread."""

    def test_delega_en_proxy_request(self):
        with patch("core.model_router.proxy.proxy_request", return_value=(200, {}, b"ok")) as mock_pr:
            result = asyncio.run(proxy._proxy_request_async("/api/chat", b"{}", "POST", "m1", "t1", "127.0.0.1"))
        assert result == (200, {}, b"ok")
        mock_pr.assert_called_once_with("/api/chat", b"{}", "POST", "m1", "t1", "127.0.0.1")

    def test_delega_por_defecto(self):
        with patch("core.model_router.proxy.proxy_request", return_value=(503, {}, b"{}")) as mock_pr:
            result = asyncio.run(proxy._proxy_request_async("/api/health", None))
        assert result[0] == 503
        mock_pr.assert_called_once_with("/api/health", None, "POST", "", "", "")


class TestProxyConGuardiaVram:
    """_proxy_con_guardia_vram delega en vram_guard.ejecutar_inferencia_segura."""

    def test_delega_en_vram_guard(self):
        guard = AsyncMock()
        guard.ejecutar_inferencia_segura.return_value = (200, {}, b"ok")
        with patch("core.model_router.vram_guard.vram_guard", guard):
            result = asyncio.run(proxy._proxy_con_guardia_vram("/api/chat", b"{}", "POST", "m1", "t1", "127.0.0.1"))
        assert result == (200, {}, b"ok")
        guard.ejecutar_inferencia_segura.assert_awaited_once()
        args = guard.ejecutar_inferencia_segura.call_args
        assert args[0][0] is proxy._proxy_request_async
        assert args[0][1:] == ("/api/chat", b"{}", "POST", "m1", "t1", "127.0.0.1")

    def test_ttl_expirado_devuelve_error(self):
        guard = AsyncMock()
        guard.ejecutar_inferencia_segura.return_value = {"error": "Timeout en cola de espera", "status_code": 504}
        with patch("core.model_router.vram_guard.vram_guard", guard):
            result = asyncio.run(proxy._proxy_con_guardia_vram("/api/chat", b"{}"))
        assert result["status_code"] == 504


class TestProxyConVram:
    """_proxy_con_vram: sin loop activo usa asyncio.run; con loop, ThreadPoolExecutor."""

    def test_sin_loop_usa_asyncio_run(self):
        with patch(
            "core.model_router.proxy._proxy_con_guardia_vram",
            new=AsyncMock(return_value=(200, {}, b"ok")),
        ) as mock_guard:
            result = proxy._proxy_con_vram("/api/chat", b"{}")
        assert result == (200, {}, b"ok")
        mock_guard.assert_awaited_once()

    def test_con_loop_usa_threadpool(self):
        async def inner() -> tuple:
            return proxy._proxy_con_vram("/api/chat", b"{}", "POST", "m1", "t1", "127.0.0.1")

        with patch(
            "core.model_router.proxy._proxy_con_guardia_vram",
            new=AsyncMock(return_value=(200, {}, b"ok")),
        ) as mock_guard:
            result = asyncio.run(inner())
        assert result == (200, {}, b"ok")
        mock_guard.assert_awaited_once()

    def test_guardia_real_end_to_end(self):
        with patch("core.model_router.proxy.proxy_request", return_value=(200, {}, b"ok")) as mock_pr:
            result = proxy._proxy_con_vram("/api/chat", b"{}")
        assert result == (200, {}, b"ok")
        mock_pr.assert_called_once()


class TestProxyRequestRamasRestantes:
    """Ramas de proxy_request no cubiertas por test_model_router_proxy.py."""

    def test_http_error_sin_modelo(self):
        err = urllib.error.HTTPError("http://x", 500, "err", None, None)
        err.read = lambda: b"oops"
        with (
            patch("core.model_router.router.POWER_MODE", "AUTO"),
            patch(
                "core.model_router.router.get_urls", return_value={"primary": "http://asus", "fallback": "http://mac"}
            ),
            patch("urllib.request.urlopen", side_effect=err),
            patch("core.model_router.metrics.metrics") as mock_metrics,
            patch("core.model_router.model_selection._record_success") as mock_record,
        ):
            status, _, body = proxy.proxy_request("/api/chat", b"{}", "POST")
        assert status == 500
        assert body == b"oops"
        mock_metrics.record_error.assert_called_with("ollama_request", "http_error", {"status": "500"})
        mock_record.assert_not_called()

    def test_urlerror_sin_modelo(self):
        with (
            patch("core.model_router.router.POWER_MODE", "AUTO"),
            patch(
                "core.model_router.router.get_urls", return_value={"primary": "http://asus", "fallback": "http://mac"}
            ),
            patch("urllib.request.urlopen", side_effect=urllib.error.URLError("down")),
            patch("core.model_router.metrics.metrics"),
            patch("core.model_router.proxy._register_fallback") as mock_fb,
            patch("core.model_router.model_selection._record_success") as mock_record,
        ):
            status, _, body = proxy.proxy_request("/api/chat", b"{}", "POST", client_ip="8.8.8.8")
        assert status == 503
        assert b"Backend local caido" in body
        mock_fb.assert_called_once()
        mock_record.assert_not_called()

    def test_turbo_caido_sin_modelo_critico(self):
        with (
            patch("core.model_router.router.POWER_MODE", "TURBO"),
            patch(
                "core.model_router.router.get_urls", return_value={"primary": "http://asus", "fallback": "http://mac"}
            ),
            patch("urllib.request.urlopen", side_effect=urllib.error.URLError("down")),
            patch("core.model_router.metrics.metrics"),
            patch("core.model_router.proxy._register_fallback"),
        ):
            status, _, body = proxy.proxy_request("/api/chat", b"{}", "POST", client_ip="127.0.0.1")
        assert status == 503
        assert b"Backend ASUS caido" in body

    def test_error_generico_con_modelo(self):
        with (
            patch("core.model_router.router.POWER_MODE", "AUTO"),
            patch(
                "core.model_router.router.get_urls", return_value={"primary": "http://asus", "fallback": "http://mac"}
            ),
            patch("urllib.request.urlopen", side_effect=ValueError("mal")),
            patch("core.model_router.metrics.metrics") as mock_metrics,
            patch("core.model_router.model_selection._record_success") as mock_record,
        ):
            status, _, body = proxy.proxy_request("/api/chat", b"{}", "POST", "m1", "t1")
        assert status == 502
        assert json.loads(body)["error"] == "mal"
        mock_record.assert_called_once_with("m1", "t1", ok=False)
        mock_metrics.increment.assert_called_once_with("model_error", {"modelo": "m1", "tipo": "t1"})

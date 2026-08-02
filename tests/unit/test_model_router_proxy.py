"""Tests for core/model_router/proxy.py — helpers y proxy_request."""

import json
import time
import urllib.error
import urllib.request
from unittest.mock import MagicMock, patch

import pytest

from core.model_router import proxy


class TestFallbackLog:
    def test_register_incrementa(self):
        proxy._fallback_log.clear()
        proxy._register_fallback()
        assert len(proxy._fallback_log) == 1

    def test_count_hour_poda_viejos(self):
        proxy._fallback_log.clear()
        proxy._fallback_log.append(time.time() - 7200)  # fuera de la ventana
        proxy._fallback_log.append(time.time())
        assert proxy._fallback_count_last_hour() == 1
        assert len(proxy._fallback_log) == 1

    def test_count_vacio(self):
        proxy._fallback_log.clear()
        assert proxy._fallback_count_last_hour() == 0

    def test_maxlen_3600(self):
        proxy._fallback_log.clear()
        for _ in range(4000):
            proxy._register_fallback()
        assert len(proxy._fallback_log) == 3600


class TestMedirAsusLatency:
    def test_ok(self):
        with (
            patch("core.model_router.router.get_urls", return_value={"primary": "http://x", "fallback": "http://y"}),
            patch("urllib.request.urlopen"),
            patch("core.model_router.proxy.time.monotonic", side_effect=[0.0, 0.05]),
        ):
            assert proxy._measare_asus_latency() == 50.0

    def test_error_devuelve_menos1(self):
        with (
            patch("core.model_router.router.get_urls", return_value={"primary": "http://x"}),
            patch("urllib.request.urlopen", side_effect=OSError("boom")),
        ):
            assert proxy._measare_asus_latency() == -1.0

    def test_update_actualiza_global(self):
        with (
            patch("core.model_router.proxy._measare_asus_latency", return_value=42.5),
            patch("core.model_router.proxy.time.time", return_value=1234.0),
        ):
            proxy._update_asus_latency()
        assert proxy._asus_latency_ms == 42.5
        assert proxy._asus_latency_updated == 1234.0


class TestBackendLabel:
    def test_turbo(self):
        with patch("core.model_router.router.POWER_MODE", "TURBO"):
            assert proxy._get_active_backend_label() == "ASUS Remoto"

    def test_eco(self):
        with patch("core.model_router.router.POWER_MODE", "ECO"):
            assert proxy._get_active_backend_label() == "Local Mac"

    def test_auto(self):
        with patch("core.model_router.router.POWER_MODE", "AUTO"):
            assert proxy._get_active_backend_label() == "AUTO (según IP)"


class TestEstimateTokens:
    def test_4_chars_por_token(self):
        assert proxy._estimate_tokens("a" * 16) == 4


class TestCheckContextSize:
    def test_str(self):
        assert proxy._check_context_size("a" * 100000)["level"] == "critical"

    def test_lista_dicts(self):
        msgs = [{"content": "a" * 50000}]
        assert proxy._check_context_size(msgs)["level"] == "warn"

    def test_lista_no_dicts(self):
        msgs = ["a" * 50000]
        assert proxy._check_context_size(msgs)["level"] == "warn"

    def test_none_ok(self):
        assert proxy._check_context_size(None)["level"] == "ok"

    def test_ok(self):
        r = proxy._check_context_size("hola")
        assert r["level"] == "ok"
        assert "Contexto normal" in r["message"]

    def test_chars_contados(self):
        r = proxy._check_context_size("hola")
        assert r["chars"] == 4


class TestIsLocalIp:
    @pytest.mark.parametrize(
        "ip, esperado",
        [
            ("127.0.0.1", True),
            ("10.164.1.26", True),
            ("192.168.1.5", True),
            ("172.20.1.1", True),
            ("8.8.8.8", False),
            ("1.2.3.4", False),
        ],
    )
    def test_prefijos(self, ip, esperado):
        assert proxy._is_local_ip(ip) is esperado


class TestResolveMode:
    def test_turbo_forzado(self):
        with patch("core.model_router.router.POWER_MODE", "TURBO"):
            assert proxy._resolve_mode_for_client("8.8.8.8") == "TURBO"

    def test_eco_forzado(self):
        with patch("core.model_router.router.POWER_MODE", "ECO"):
            assert proxy._resolve_mode_for_client("127.0.0.1") == "ECO"

    def test_auto_local_turbo(self):
        with patch("core.model_router.router.POWER_MODE", "AUTO"):
            assert proxy._resolve_mode_for_client("10.1.1.1") == "TURBO"

    def test_auto_remoto_eco(self):
        with patch("core.model_router.router.POWER_MODE", "AUTO"):
            assert proxy._resolve_mode_for_client("8.8.8.8") == "ECO"


class TestResolveOllamaUrl:
    def test_env_forzada(self, monkeypatch):
        monkeypatch.setenv("OLLAMA_URL", "http://especial:1")
        assert proxy._resolve_ollama_url() == "http://especial:1"

    def test_primary_accesible(self):
        with (
            patch("core.model_router.router.get_urls", return_value={"primary": "http://asus", "fallback": "http://mac"}),
            patch("urllib.request.urlopen"),
        ):
            assert proxy._resolve_ollama_url() == "http://asus"

    def test_fallback_en_error(self):
        with (
            patch("core.model_router.router.get_urls", return_value={"primary": "http://asus", "fallback": "http://mac"}),
            patch("urllib.request.urlopen", side_effect=OSError("down")),
        ):
            assert proxy._resolve_ollama_url() == "http://mac"


class TestProxyRequest:
    def _mock_urlopen(self, status=200, body=b"ok", headers=None):
        resp = MagicMock()
        resp.__enter__.return_value = resp
        resp.__exit__.return_value = False
        resp.status = status
        resp.headers = headers or {"x": "1"}
        resp.read.return_value = body
        return patch("urllib.request.urlopen", return_value=resp)

    def test_ok_devuelve_tuple(self):
        with (
            patch("core.model_router.router.POWER_MODE", "AUTO"),
            patch("core.model_router.router.get_urls", return_value={"primary": "http://asus", "fallback": "http://mac"}),
            self._mock_urlopen(200, b'{"ok": true}'),
        ):
            status, headers, body = proxy.proxy_request("/api/tags", b"{}", "GET")
        assert status == 200
        assert body == b'{"ok": true}'

    def test_ok_registra_metricas_con_modelo(self):
        with (
            patch("core.model_router.router.POWER_MODE", "AUTO"),
            patch("core.model_router.router.get_urls", return_value={"primary": "http://asus", "fallback": "http://mac"}),
            patch("core.model_router.metrics.metrics") as mock_metrics,
            patch("core.model_router.model_selection._record_success") as mock_record,
            self._mock_urlopen(200, b"ok"),
        ):
            status, _, _ = proxy.proxy_request("/api/chat", b"{}", "POST", "m1", "t1")
        assert status == 200
        mock_record.assert_called_once_with("m1", "t1", ok=True)
        mock_metrics.increment.assert_called_once_with("model_success", {"modelo": "m1", "tipo": "t1"})
        mock_metrics.record_latency.assert_called_once()

    def test_http_error(self):
        err = urllib.error.HTTPError("http://x", 429, "limit", None, None)
        err.read = lambda: b"slow down"
        with (
            patch("core.model_router.router.POWER_MODE", "AUTO"),
            patch("core.model_router.router.get_urls", return_value={"primary": "http://asus", "fallback": "http://mac"}),
            patch("urllib.request.urlopen", side_effect=err),
            patch("core.model_router.metrics.metrics") as mock_metrics,
        ):
            status, _, body = proxy.proxy_request("/api/chat", b"{}", "POST", "m1", "t1")
        assert status == 429
        assert body == b"slow down"
        mock_metrics.record_error.assert_called_with("ollama_request", "http_error", {"status": "429"})

    def test_urlerror_503(self):
        with (
            patch("core.model_router.router.POWER_MODE", "AUTO"),
            patch("core.model_router.router.get_urls", return_value={"primary": "http://asus", "fallback": "http://mac"}),
            patch("urllib.request.urlopen", side_effect=urllib.error.URLError("down")),
            patch("core.model_router.metrics.metrics"),
        ):
            status, _, body = proxy.proxy_request("/api/chat", b"{}", "POST", "m1", "t1", "8.8.8.8")
        assert status == 503
        assert b'"error"' in body
        assert b"Backend local caido" in body

    def test_timeout_503(self):
        with (
            patch("core.model_router.router.POWER_MODE", "AUTO"),
            patch("core.model_router.router.get_urls", return_value={"primary": "http://asus", "fallback": "http://mac"}),
            patch("urllib.request.urlopen", side_effect=TimeoutError("t")),
            patch("core.model_router.metrics.metrics"),
            patch("core.model_router.proxy._register_fallback") as mock_fb,
        ):
            status, _, _ = proxy.proxy_request("/api/chat", b"{}", "POST", "m1", "t1", "127.0.0.1")
        assert status == 503
        mock_fb.assert_called_once()

    def test_error_generico_502(self):
        with (
            patch("core.model_router.router.POWER_MODE", "AUTO"),
            patch("core.model_router.router.get_urls", return_value={"primary": "http://asus", "fallback": "http://mac"}),
            patch("urllib.request.urlopen", side_effect=ValueError("mal")),
            patch("core.model_router.metrics.metrics"),
        ):
            status, _, body = proxy.proxy_request("/api/chat", b"{}", "POST")
        assert status == 502
        assert json.loads(body)["error"] == "mal"

    def test_turbo_caido_mensaje_critico(self):
        with (
            patch("core.model_router.router.POWER_MODE", "TURBO"),
            patch("core.model_router.router.get_urls", return_value={"primary": "http://asus", "fallback": "http://mac"}),
            patch("urllib.request.urlopen", side_effect=urllib.error.URLError("down")),
            patch("core.model_router.metrics.metrics"),
        ):
            status, _, body = proxy.proxy_request("/api/chat", b"{}", "POST", "m1", "t1", "127.0.0.1")
        assert status == 503
        assert b"Backend ASUS caido" in body

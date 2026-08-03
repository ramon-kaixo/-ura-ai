"""Tests para core/model_router/router.py — URLs, auth, rate_limiter."""
from __future__ import annotations

from unittest import mock

import core.model_router.router as r


class TestNoOpRateLimiter:
    def test_import_fallback(self, monkeypatch) -> None:
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *a, **k):
            if name == "router_rate_limiter":
                raise ImportError("no instalado")
            return real_import(name, *a, **k)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        import importlib

        importlib.reload(r)
        assert r.rate_limiter.check() is True
        assert r.rate_limiter.is_allowed() is True
        assert r.rate_limiter.wait_if_needed() is None
        assert r.rate_limiter.get_metrics() == {}
        importlib.reload(r)  # restaurar

    def test_rate_limiter_real_importado(self) -> None:
        assert r.rate_limiter is not None


class TestAuthFallback:
    def test_auth_validate_default(self) -> None:
        # Si auth_layer importa bien, auth_validate es la real
        assert callable(r.auth_validate)

    def test_require_auth_callable(self) -> None:
        assert callable(r.require_auth)


class TestGetUrls:
    def test_cached(self, monkeypatch) -> None:
        monkeypatch.setattr(r, "_URLS", {"primary": "a", "fallback": "b"})
        assert r.get_urls() == {"primary": "a", "fallback": "b"}

    def test_llama_config(self, monkeypatch) -> None:
        monkeypatch.setattr(r, "_URLS", None)
        monkeypatch.setattr(r, "get_ollama_urls", mock.Mock(return_value={"primary": "p", "fallback": "f"}))
        assert r.get_urls() == {"primary": "p", "fallback": "f"}
        assert r._URLS == {"primary": "p", "fallback": "f"}


class TestResolveOllamaUrl:
    def test_env_forzada(self, monkeypatch) -> None:
        monkeypatch.setenv("OLLAMA_URL", "http://custom:11434")
        monkeypatch.setattr(r, "get_urls", mock.Mock(return_value={"primary": "p", "fallback": "f"}))
        assert r._resolve_ollama_url() == "http://custom:11434"

    def test_primary_conecta(self, monkeypatch) -> None:
        monkeypatch.delenv("OLLAMA_URL", raising=False)
        monkeypatch.setattr(r, "get_urls", mock.Mock(return_value={"primary": "http://asus:11434", "fallback": "http://local:11434"}))
        resp = mock.Mock()
        resp.__enter__ = mock.Mock(return_value=resp)
        resp.__exit__ = mock.Mock(return_value=False)
        monkeypatch.setattr("core.model_router.router.urllib.request.urlopen", mock.Mock(return_value=resp))
        assert r._resolve_ollama_url() == "http://asus:11434"

    def test_primary_falla_usar_fallback(self, monkeypatch) -> None:
        monkeypatch.delenv("OLLAMA_URL", raising=False)
        monkeypatch.setattr(r, "get_urls", mock.Mock(return_value={"primary": "http://asus:11434", "fallback": "http://local:11434"}))
        monkeypatch.setattr("core.model_router.router.urllib.request.urlopen", mock.Mock(side_effect=OSError("no red")))
        assert r._resolve_ollama_url() == "http://local:11434"

    def test_connection_header(self, monkeypatch) -> None:
        monkeypatch.delenv("OLLAMA_URL", raising=False)
        monkeypatch.setattr(r, "get_urls", mock.Mock(return_value={"primary": "http://asus:11434", "fallback": "f"}))
        req_mock = mock.Mock()
        req_mock.add_header = mock.Mock()
        monkeypatch.setattr("core.model_router.router.urllib.request.Request", mock.Mock(return_value=req_mock))
        resp = mock.Mock()
        resp.__enter__ = mock.Mock(return_value=resp)
        resp.__exit__ = mock.Mock(return_value=False)
        monkeypatch.setattr("core.model_router.router.urllib.request.urlopen", mock.Mock(return_value=resp))
        r._resolve_ollama_url()
        req_mock.add_header.assert_called_once_with("Connection", "close")


class TestGetOllamaUrl:
    def test_cachea(self, monkeypatch) -> None:
        monkeypatch.setattr(r, "_OLLAMA_URL", None)
        resolver = mock.Mock(return_value="http://x:11434")
        monkeypatch.setattr(r, "_resolve_ollama_url", resolver)
        assert r.get_ollama_url() == "http://x:11434"
        assert r.get_ollama_url() == "http://x:11434"
        resolver.assert_called_once()


class TestConstantes:
    def test_constantes(self) -> None:
        assert r.ROUTER_PORT == 11435
        assert r.DEFAULT_TIPO == "respuesta_rapida"
        assert r.FALLBACK_MODEL == "qwen2.5:3b"
        assert r.CACHE_TTL == 7200


class TestAuthFallbackReal:
    def test_fallback_por_import_error(self, monkeypatch) -> None:
        """El branch except ImportError del auth fallback en router.py."""
        import builtins
        import importlib

        import core.model_router.router as r

        real_import = builtins.__import__

        def fake_import(name, *a, **k):
            if name == "core.auth_layer":
                raise ImportError("simulado")
            return real_import(name, *a, **k)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        importlib.reload(r)
        assert r.auth_validate("x") is True
        assert r.require_auth()(lambda: 1) is not None
        importlib.reload(r)  # restaurar

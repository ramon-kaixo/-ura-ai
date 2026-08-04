"""Tests para motor/core/llm/router/ — utils, capability, health, providers."""
from __future__ import annotations

import threading
from types import SimpleNamespace

import pytest

from motor.core.llm.router.capability import find_providers_by_capability, select_provider_by_capability
from motor.core.llm.router.health import health_get_cached, health_remove_cache, health_store_cache
from motor.core.llm.router.providers import DEFAULT_ROUTES, resolve, resolve_name
from motor.core.llm.router.utils import _build_error, _classify_error, _is_error_result


class TestClassifyError:
    def test_timeout(self) -> None:
        import httpx

        assert _classify_error(httpx.TimeoutException("t")) == "timeout"

    def test_connect(self) -> None:
        import httpx

        assert _classify_error(httpx.ConnectError("c")) == "connection_error"

    def test_protocol(self) -> None:
        import httpx

        assert _classify_error(httpx.RemoteProtocolError("p")) == "protocol_error"

    def test_http_status(self) -> None:
        import httpx

        resp = httpx.Response(503, request=httpx.Request("GET", "http://x"))
        assert _classify_error(httpx.HTTPStatusError("e", request=resp.request, response=resp)) == "http_503"

    def test_generico(self) -> None:
        assert _classify_error(ValueError("v")) == "unexpected:ValueError"

    def test_sin_httpx(self, monkeypatch) -> None:
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *a, **k):
            if name == "httpx":
                raise ImportError("no")
            return real_import(name, *a, **k)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        assert _classify_error(ValueError("x")) == "error"


class TestIsErrorResult:
    def test_prefijo_error(self) -> None:
        assert _is_error_result("Error: algo") is True

    def test_no_error(self) -> None:
        assert _is_error_result("respuesta") is False
        assert _is_error_result({"a": 1}) is False
        assert _is_error_result(None) is False


class TestBuildError:
    def test_embed(self) -> None:
        out = _build_error("embed", "fallo")
        assert isinstance(out, list)
        assert len(out[0]) > 0
        assert all(x == 0.0 for x in out[0])

    def test_embed_async(self) -> None:
        out = _build_error("embed_async", "fallo")
        assert isinstance(out, list)

    def test_otros(self) -> None:
        assert _build_error("generate", "boom") == "Error: boom"


class FakeRegistry:
    def __init__(self, providers: dict):
        self._providers = providers
        self._default = "ollama"

    def list(self):
        return list(self._providers)

    def get(self, name):
        return self._providers[name]

    def __contains__(self, name):
        return name in self._providers

    @property
    def default_name(self):
        return self._default


class TestFindProvidersByCapability:
    def test_encuentra(self) -> None:
        reg = FakeRegistry({"a": SimpleNamespace(supports=lambda c: c == "embed"), "b": SimpleNamespace(supports=lambda c: True)})
        assert find_providers_by_capability("embed", reg) == ["a", "b"]

    def test_error_check_ignorado(self) -> None:
        reg = FakeRegistry({"a": SimpleNamespace(supports=lambda c: (_ for _ in ()).throw(RuntimeError("x"))), "b": SimpleNamespace(supports=lambda c: True)})
        assert find_providers_by_capability("c", reg) == ["b"]


class TestSelectProviderByCapability:
    def test_preferred_ok(self) -> None:
        reg = FakeRegistry({"pref": SimpleNamespace(supports=lambda c: True), "b": SimpleNamespace(supports=lambda c: True)})
        assert select_provider_by_capability("c", "pref", reg) == "pref"

    def test_preferred_no_soporta_fallback(self) -> None:
        reg = FakeRegistry({"pref": SimpleNamespace(supports=lambda c: False), "b": SimpleNamespace(supports=lambda c: True)})
        assert select_provider_by_capability("c", "pref", reg) == "b"

    def test_preferred_supports_raise_fallback(self) -> None:
        reg = FakeRegistry(
            {"pref": SimpleNamespace(supports=lambda c: (_ for _ in ()).throw(RuntimeError("x"))), "b": SimpleNamespace(supports=lambda c: True)}
        )
        assert select_provider_by_capability("c", "pref", reg) == "b"

    def test_preferred_keyerror_fallback(self) -> None:
        reg = FakeRegistry({"b": SimpleNamespace(supports=lambda c: True)})
        assert select_provider_by_capability("c", "fantasma", reg) == "b"

    def test_sin_capaz_raise(self) -> None:
        reg = FakeRegistry({"a": SimpleNamespace(supports=lambda c: False)})
        with pytest.raises(RuntimeError, match="No provider supports"):
            select_provider_by_capability("c", None, reg)


class TestHealthCache:
    def test_store_y_get(self) -> None:
        cache: dict = {}
        lock = threading.Lock()
        health_store_cache("p", {"ok": True}, cache, lock)
        out = health_get_cached("p", cache, lock, 100.0)
        assert out == {"ok": True}

    def test_get_sin_entrada(self) -> None:
        cache: dict = {}
        lock = threading.Lock()
        assert health_get_cached("p", cache, lock, 100.0) is None
        assert "p" in cache  # marcado en progreso (0.0, None)

    def test_ttl_expirado(self, monkeypatch) -> None:
        cache: dict = {"p": (0.0, {"ok": True})}
        lock = threading.Lock()
        monkeypatch.setattr("motor.core.llm.router.health.time.monotonic", lambda: 99999)
        out = health_get_cached("p", cache, lock, 100.0)
        assert out is None  # expirado -> re-marca en progreso

    def test_espera_en_progreso(self, monkeypatch) -> None:
        cache: dict = {"p": (0.0, None)}
        lock = threading.Lock()

        def fake_sleep(s):
            # segunda lectura: otro hilo ya puso resultado
            if cache["p"][1] is None:
                cache["p"] = (1.0, {"ok": True})

        monkeypatch.setattr("motor.core.llm.router.health.time.sleep", fake_sleep)
        out = health_get_cached("p", cache, lock, 100.0)
        assert out == {"ok": True}

    def test_remove(self) -> None:
        cache: dict = {"p": (1.0, {})}
        lock = threading.Lock()
        health_remove_cache("p", cache, lock)
        assert "p" not in cache

    def test_remove_inexistente(self) -> None:
        cache: dict = {}
        lock = threading.Lock()
        health_remove_cache("p", cache, lock)  # no debe lanzar


class TestResolve:
    def test_provider_explicito(self) -> None:
        reg = FakeRegistry({"ollama": object()})
        out = resolve("generate", "ollama", reg, DEFAULT_ROUTES)
        assert out is not None

    def test_provider_no_registrado(self) -> None:
        reg = FakeRegistry({"ollama": object()})
        with pytest.raises(RuntimeError, match="not in registry"):
            resolve("generate", "nope", reg, DEFAULT_ROUTES)

    def test_por_ruta(self) -> None:
        prov = object()
        reg = FakeRegistry({"ollama": prov})
        assert resolve("generate", None, reg, DEFAULT_ROUTES) is prov

    def test_ruta_no_existe_default(self) -> None:
        prov = object()
        reg = FakeRegistry({"ollama": prov})
        assert resolve("tarea_rara", None, reg, DEFAULT_ROUTES) is prov

    def test_sin_default_raise(self) -> None:
        reg = FakeRegistry({})
        reg._default = None
        with pytest.raises(RuntimeError, match="No provider available"):
            resolve("tarea", None, reg, {})

    def test_ruta_no_registrada_fallback_default(self) -> None:
        prov = object()
        reg = FakeRegistry({"ollama": prov})
        assert resolve("tarea", None, reg, {"tarea": "noexiste"}) is prov

    def test_ruta_no_registrada_sin_default_raise(self) -> None:
        reg = FakeRegistry({})
        reg._default = None
        with pytest.raises(RuntimeError, match="unregistered"):
            resolve("tarea", None, reg, {"tarea": "fantasma"})


class TestResolveName:
    def test_provider_explicito(self) -> None:
        reg = FakeRegistry({"ollama": object()})
        assert resolve_name("g", "ollama", reg, DEFAULT_ROUTES) == "ollama"

    def test_por_ruta(self) -> None:
        reg = FakeRegistry({"ollama": object()})
        assert resolve_name("generate", None, reg, DEFAULT_ROUTES) == "ollama"

    def test_ruta_no_registrada_default(self) -> None:
        reg = FakeRegistry({"ollama": object()})
        assert resolve_name("t", None, reg, {"t": "nope"}) == "ollama"

    def test_desconocido(self) -> None:
        reg = FakeRegistry({})
        reg._default = None
        assert resolve_name("t", None, reg, {}) == "unknown"

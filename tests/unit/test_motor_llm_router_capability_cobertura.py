"""Tests de cobertura (100x100) de motor/core/llm/router/{capability,providers,health,utils}."""

from __future__ import annotations

import threading
import time

import pytest

import motor.core.llm.router.health as health_mod
from motor.core.llm.base import FALLBACK_EMBEDDING_DIMENSION
from motor.core.llm.router import capability, providers, utils


class FakeProvider:
    def __init__(
        self,
        supports: bool | Exception = True,
        health_result=None,
        provider_name: str = "p",
    ) -> None:
        self._supports = supports
        self._health = health_result or {"status": "ok"}
        self.name = provider_name

    def generate(self, prompt, **kwargs):  # pragma: no cover - solo API
        return "ok"

    def embed(self, texts, **kwargs):  # pragma: no cover - solo API
        return [[0.1] * 4 for _ in texts]

    async def embed_async(self, texts, **kwargs):  # pragma: no cover - solo API
        return [[0.1] * 4 for _ in texts]

    def health(self):
        return dict(self._health)

    def supports(self, capability: str) -> bool:
        if isinstance(self._supports, Exception):
            raise self._supports
        return self._supports


class FakeRegistry:
    def __init__(self, providers: dict, default=None) -> None:
        self._providers = providers
        self._default = default

    def list(self):
        return list(self._providers)

    def get(self, name):
        return self._providers[name]

    def __contains__(self, name):
        return name in self._providers

    @property
    def default_name(self):
        return self._default


# ---------------------------------------------------------------------------
# capability.py
# ---------------------------------------------------------------------------


class TestFindProvidersByCapability:
    def test_filtra_soportados(self) -> None:
        reg = FakeRegistry(
            {"a": FakeProvider(supports=True), "b": FakeProvider(supports=False)},
            default="a",
        )
        assert capability.find_providers_by_capability("embed", reg) == ["a"]

    def test_ignora_proveedor_que_falla(self) -> None:
        reg = FakeRegistry(
            {"a": FakeProvider(supports=RuntimeError("boom")), "b": FakeProvider(supports=True)},
            default="b",
        )
        assert capability.find_providers_by_capability("embed", reg) == ["b"]


class TestSelectProviderByCapability:
    def test_preferred_que_soporta(self) -> None:
        reg = FakeRegistry({"a": FakeProvider(supports=True)}, default="a")
        assert capability.select_provider_by_capability("embed", "a", reg) == "a"

    def test_preferred_soporta_true_cuando_lanza(self) -> None:
        reg = FakeRegistry(
            {"a": FakeProvider(supports=False), "b": FakeProvider(supports=True)},
            default="b",
        )
        out = capability.select_provider_by_capability("embed", "a", reg)
        assert out == "b"

    def test_preferred_no_registrado_cae_a_find(self) -> None:
        reg = FakeRegistry({"b": FakeProvider(supports=True)}, default="b")
        assert capability.select_provider_by_capability("embed", "missing", reg) == "b"

    def test_ninguno_soporta_raise(self) -> None:
        reg = FakeRegistry({"a": FakeProvider(supports=False)}, default="a")
        with pytest.raises(RuntimeError, match="No provider supports"):
            capability.select_provider_by_capability("embed", None, reg)


# ---------------------------------------------------------------------------
# providers.py
# ---------------------------------------------------------------------------


class TestResolve:
    def test_provider_explicito_valido(self) -> None:
        reg = FakeRegistry({"a": FakeProvider(provider_name="a")}, default="a")
        assert providers.resolve("generate", "a", reg, {"generate": "a"}) is reg.get("a")

    def test_provider_explicito_no_registrado(self) -> None:
        reg = FakeRegistry({"a": FakeProvider()}, default="a")
        with pytest.raises(RuntimeError, match="not in registry"):
            providers.resolve("generate", "nope", reg, {})

    def test_ruta_valida(self) -> None:
        reg = FakeRegistry({"a": FakeProvider()}, default="a")
        assert providers.resolve("generate", None, reg, {"generate": "a"}) is reg.get("a")

    def test_sin_default_y_ruta_ausente(self) -> None:
        reg = FakeRegistry({}, default=None)
        with pytest.raises(RuntimeError, match="Register a provider"):
            providers.resolve("embed", None, reg, {})

    def test_ruta_a_proveedor_no_registrado_con_default(self) -> None:
        reg = FakeRegistry({"b": FakeProvider()}, default="b")
        assert providers.resolve("embed", None, reg, {"embed": "ghost"}) is reg.get("b")

    def test_ruta_a_proveedor_no_registrado_y_default_none(self) -> None:
        reg = FakeRegistry({}, default=None)
        with pytest.raises(RuntimeError, match="no fallback default"):
            providers.resolve("embed", None, reg, {"embed": "ghost"})


class TestResolveName:
    def test_provider_explicito(self) -> None:
        assert providers.resolve_name("generate", "a", FakeRegistry({}), {}) == "a"

    def test_ruta_o_default(self) -> None:
        reg = FakeRegistry({"a": FakeProvider()}, default="a")
        assert providers.resolve_name("generate", None, reg, {"generate": "a"}) == "a"

    def test_ruta_no_registrada_devuelve_default(self) -> None:
        reg = FakeRegistry({"b": FakeProvider()}, default="b")
        assert providers.resolve_name("embed", None, reg, {"embed": "ghost"}) == "b"

    def test_none_returns_unknown(self) -> None:
        reg = FakeRegistry({}, default=None)
        assert providers.resolve_name("generate", None, reg, {}) == "unknown"


# ---------------------------------------------------------------------------
# utils.py
# ---------------------------------------------------------------------------


class TestClassifyError:
    def test_timeout(self) -> None:
        import httpx

        assert utils._classify_error(httpx.TimeoutException("t")) == "timeout"

    def test_connect_error(self) -> None:
        import httpx

        assert utils._classify_error(httpx.ConnectError("c")) == "connection_error"

    def test_protocol_error(self) -> None:
        import httpx

        assert utils._classify_error(httpx.RemoteProtocolError("p")) == "protocol_error"

    def test_http_status(self) -> None:
        import httpx

        resp = httpx.Response(404, request=httpx.Request("GET", "http://x"))
        err = httpx.HTTPStatusError("e", request=resp.request, response=resp)
        assert utils._classify_error(err) == "http_404"

    def test_otro(self) -> None:
        assert utils._classify_error(ValueError("x")) == "unexpected:ValueError"

    def test_sin_httpx(self, monkeypatch) -> None:
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *a, **k):
            if name == "httpx":
                raise ImportError("no httpx")
            return real_import(name, *a, **k)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        assert utils._classify_error(ValueError("x")) == "error"


class TestIsErrorResult:
    def test_str_prefijo(self) -> None:
        assert utils._is_error_result("Error: algo") is True

    def test_no_str(self) -> None:
        assert utils._is_error_result({"a": 1}) is False


class TestBuildError:
    def test_embed_devuelve_fallback(self) -> None:
        out = utils._build_error("embed", "boom")
        assert out == [[0.0] * FALLBACK_EMBEDDING_DIMENSION]

    def test_embed_async_devuelve_fallback(self) -> None:
        out = utils._build_error("embed_async", "boom")
        assert out == [[0.0] * FALLBACK_EMBEDDING_DIMENSION]

    def test_generate_devuelve_prefijo(self) -> None:
        assert utils._build_error("generate", "boom") == "Error: boom"


# ---------------------------------------------------------------------------
# health.py
# ---------------------------------------------------------------------------


class TestHealthGetCached:
    def test_cache_vacio_devuelve_none_y_stamp(self) -> None:
        cache: dict = {}
        lock = threading.Lock()
        out = health_mod.health_get_cached("a", cache, lock, 60.0)
        assert out is None
        assert cache.get("a") == (0.0, None)

    def test_cache_fresca_devuelve_valor(self) -> None:
        cache = {"a": (time.monotonic(), {"status": "ok"})}
        out = health_mod.health_get_cached("a", cache, threading.Lock(), 60.0)
        assert out == {"status": "ok"}

    def test_cache_expirada_devuelve_none(self) -> None:
        cache = {"a": (time.monotonic() - 1000.0, {"status": "ok"})}
        out = health_mod.health_get_cached("a", cache, threading.Lock(), 60.0)
        assert out is None
        assert cache["a"] == (0.0, None)

    def test_in_flight_que_se_completa(self) -> None:
        cache: dict = {"a": (0.0, None)}
        lock = threading.Lock()
        done = {"flag": False}

        def completar() -> None:
            time.sleep(0.01)
            with lock:
                cache["a"] = (time.monotonic(), {"status": "ok"})
            done["flag"] = True

        t = threading.Thread(target=completar)
        t.start()
        out = health_mod.health_get_cached("a", cache, lock, 60.0)
        t.join()
        assert out == {"status": "ok"}
        assert done["flag"] is True

    def test_in_flight_no_se_completa_sale_y_reestamp(self) -> None:
        cache: dict = {"a": (0.0, None)}
        out = health_mod.health_get_cached("a", cache, threading.Lock(), 60.0)
        assert out is None
        assert cache["a"] == (0.0, None)


class TestHealthStoreRemove:
    def test_store(self) -> None:
        cache: dict = {}
        health_mod.health_store_cache("a", {"status": "ok"}, cache, threading.Lock())
        assert cache["a"][1] == {"status": "ok"}

    def test_remove(self) -> None:
        cache = {"a": (1.0, {"status": "ok"})}
        health_mod.health_remove_cache("a", cache, threading.Lock())
        assert "a" not in cache

    def test_remove_inexistente_no_falla(self) -> None:
        cache: dict = {}
        health_mod.health_remove_cache("x", cache, threading.Lock())
        assert cache == {}

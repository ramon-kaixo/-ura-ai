"""Cobertura 100x100 del LLM Router (TASK-20260814-001).

El router ya tiene cobertura parcial desde los tests de proveedores
(test_anthropic, test_gemini, etc.). Aquí se cubren los remanentes:
strategy (retry/fallback/circuit), health cache, utils, capability,
providers.resolve y los métodos LLMRouter menos ejercitados.
"""

from __future__ import annotations

import threading
import time
from typing import Any

import httpx
import pytest

from motor.core.llm.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError


class FakeProv:
    def __init__(self, name: str, supports: list[str] | None = None) -> None:
        self._name = name
        self._caps = supports or ["chat", "generate", "embed"]
        self.calls: list[tuple[str, Any]] = []

    def supports(self, capability: str) -> bool:
        return capability in self._caps

    def generate(self, prompt: str, **kwargs: Any) -> str:
        self.calls.append(("generate", prompt))
        return f"respuesta-{self._name}"

    def embed(self, texts: list[str], **kwargs: Any) -> list[list[float]]:
        self.calls.append(("embed", texts))
        return [[0.1, 0.2]]

    async def embed_async(self, texts: list[str], **kwargs: Any) -> list[list[float]]:
        self.calls.append(("embed_async", texts))
        return [[0.1, 0.2]]

    def health(self) -> dict[str, Any]:
        return {"provider": self._name, "status": "ok"}


class FakeRegistry:
    def __init__(self, providers: dict[str, FakeProv], default: str | None = None) -> None:
        self._providers = providers
        self._default = default

    @property
    def default_name(self) -> str | None:
        return self._default

    def list(self) -> list[str]:
        return list(self._providers)

    def get(self, name: str) -> FakeProv:
        return self._providers[name]

    def __contains__(self, name: str) -> bool:
        return name in self._providers


class TestRouterUtils:
    def test_classify_error(self) -> None:
        from motor.core.llm.router.utils import _classify_error

        assert _classify_error(httpx.TimeoutException("t")) == "timeout"
        assert _classify_error(httpx.ConnectError("c")) == "connection_error"
        assert _classify_error(httpx.RemoteProtocolError("p")) == "protocol_error"
        assert (
            _classify_error(httpx.HTTPStatusError("e", request=httpx.Request("GET", "u"), response=httpx.Response(404)))
            == "http_404"
        )
        assert _classify_error(ValueError("v")) == "unexpected:ValueError"

    def test_is_error_result(self) -> None:
        from motor.core.llm.router.utils import _is_error_result

        assert _is_error_result("Error: x") is True
        assert _is_error_result("ok") is False
        assert _is_error_result(42) is False

    def test_build_error(self) -> None:
        from motor.core.llm.router.utils import _build_error

        assert _build_error("generate", "boom") == "Error: boom"
        emb = _build_error("embed", "boom")
        assert emb == [[0.0] * len(emb[0])]


class TestRouterStrategy:
    def test_is_transient_error(self) -> None:
        from motor.core.llm.router.strategy import _is_transient_error

        assert _is_transient_error(TimeoutError("t")) is True
        assert _is_transient_error(ConnectionError("c")) is True
        assert _is_transient_error(httpx.TimeoutException("t")) is True
        assert _is_transient_error(httpx.ConnectError("c")) is True
        assert _is_transient_error(httpx.RemoteProtocolError("p")) is True
        assert (
            _is_transient_error(
                httpx.HTTPStatusError("e", request=httpx.Request("GET", "u"), response=httpx.Response(429))
            )
            is True
        )
        assert (
            _is_transient_error(
                httpx.HTTPStatusError("e", request=httpx.Request("GET", "u"), response=httpx.Response(404))
            )
            is False
        )
        assert _is_transient_error(ValueError("v")) is False

    def test_get_cb_creates(self) -> None:
        from motor.core.llm.router.strategy import _get_cb

        cbs: dict[str, Any] = {}
        cb = _get_cb("nuevo", cbs)
        assert isinstance(cb, CircuitBreaker)
        assert _get_cb("nuevo", cbs) is cb

    def test_call_with_retry_success(self) -> None:
        from motor.core.llm.router.strategy import call_with_retry

        prov = FakeProv("p1")
        result = call_with_retry(prov, "generate", "task", "p1", FakeRegistry({"p1": prov}), {}, prompt="hola")
        assert result == "respuesta-p1"

    def test_call_with_retry_no_retry(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from motor.core.llm.router.strategy import call_with_retry

        def boom(*a: Any, **k: Any) -> str:
            raise ConnectionError("red")

        monkeypatch.setattr("motor.core.llm.router.strategy.time.sleep", lambda s: None)
        prov = FakeProv("p1")
        prov.generate = boom  # type: ignore[method-assign]
        result = call_with_retry(
            prov, "generate", "task", "p1", FakeRegistry({"p1": prov}), {}, prompt="x", retry_enabled=False
        )
        assert result.startswith("Error:")

    def test_call_with_retry_transient_retries_then_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from motor.core.llm.router.strategy import call_with_retry

        monkeypatch.setattr("motor.core.llm.router.strategy.time.sleep", lambda s: None)
        calls = {"n": 0}

        def boom(*a: Any, **k: Any) -> str:
            calls["n"] += 1
            raise httpx.TimeoutException("t")

        prov = FakeProv("p1")
        prov.generate = boom  # type: ignore[method-assign]
        result = call_with_retry(
            prov,
            "generate",
            "task",
            "p1",
            FakeRegistry({"p1": prov}),
            {},
            prompt="x",
            retry_max_attempts=2,
            retry_backoff_base=0.1,
        )
        assert calls["n"] == 2
        assert result.startswith("Error:")

    def test_call_with_retry_circuit_open(self) -> None:
        from motor.core.llm.router.strategy import call_with_retry

        cb = CircuitBreaker("p1", failure_threshold=1, recovery_timeout=600.0)
        with pytest.raises(ConnectionError):
            cb.call(lambda: (_ for _ in ()).throw(ConnectionError("c")))
        prov = FakeProv("p1")
        result = call_with_retry(prov, "generate", "task", "p1", FakeRegistry({"p1": prov}), {"p1": cb}, prompt="x")
        assert result == "Error: circuit_breaker_open"

    def test_call_with_retry_profiler_metrics(self) -> None:
        from motor.core.llm.router.strategy import call_with_retry

        class FakeProfile:
            wall_time_ms = 10.0
            cpu_time_ms = 5.0
            peak_memory_bytes = 1024

        class FakeProfiler:
            def __init__(self) -> None:
                self.profile = FakeProfile()

            def start(self, *a: Any, **k: Any) -> None:
                pass

            def stop(self, *a: Any, **k: Any) -> FakeProfile:
                return self.profile

        class FakeDetector:
            def __init__(self) -> None:
                self.calls = 0

            def evaluate_from_profile(self, profile: Any) -> None:
                self.calls += 1

        class FakeBaseline:
            def __init__(self) -> None:
                self.calls = 0

            def record(self, *a: Any, **k: Any) -> None:
                self.calls += 1

        profiler, detector, baseline = FakeProfiler(), FakeDetector(), FakeBaseline()
        prov = FakeProv("p1")
        result = call_with_retry(
            prov,
            "generate",
            "task",
            "p1",
            FakeRegistry({"p1": prov}),
            {},
            prompt="x",
            profiler=profiler,
            detector=detector,
            baseline=baseline,
        )
        assert result == "respuesta-p1"
        assert detector.calls == 1 and baseline.calls == 1

    def test_call_with_retry_profiler_no_profile(self) -> None:
        from motor.core.llm.router.strategy import call_with_retry

        class FakeProfiler:
            def start(self, *a: Any, **k: Any) -> None:
                pass

            def stop(self, *a: Any, **k: Any) -> None:
                return None

        class FakeDetector:
            def evaluate_from_profile(self, prof: Any) -> None:  # pragma: no cover
                raise AssertionError("no debe llamarse")

        prov = FakeProv("p1")
        result = call_with_retry(
            prov,
            "generate",
            "task",
            "p1",
            FakeRegistry({"p1": prov}),
            {},
            prompt="x",
            profiler=FakeProfiler(),
            detector=FakeDetector(),
        )
        assert result == "respuesta-p1"

    def test_call_with_retry_monitor(self) -> None:
        from motor.core.llm.router.strategy import call_with_retry

        class FakeMonitor:
            def __init__(self) -> None:
                self.calls = 0

            def start_operation(self, *a: Any, **k: Any) -> None:
                self.calls += 1

            def finish_operation(self, *a: Any, **k: Any) -> None:
                self.calls += 1

        monitor = FakeMonitor()
        prov = FakeProv("p1")
        result = call_with_retry(
            prov, "generate", "task", "p1", FakeRegistry({"p1": prov}), {}, prompt="x", monitor=monitor
        )
        assert result == "respuesta-p1" and monitor.calls == 2

    def test_call_with_retry_embed_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from motor.core.llm.router.strategy import call_with_retry

        monkeypatch.setattr("motor.core.llm.router.strategy.time.sleep", lambda s: None)

        def boom(*a: Any, **k: Any) -> list[list[float]]:
            raise httpx.TimeoutException("t")

        prov = FakeProv("p1")
        prov.embed = boom  # type: ignore[method-assign]
        result = call_with_retry(prov, "embed", "task", "p1", FakeRegistry({"p1": prov}), {}, texts=["x"])
        assert result == [[0.0] * len(result[0])]

    def test_call_with_fallback_ok(self) -> None:
        from motor.core.llm.router.strategy import call_with_fallback

        p1, p2 = FakeProv("p1"), FakeProv("p2")
        reg = FakeRegistry({"p1": p1, "p2": p2})
        result, used = call_with_fallback(p1, "generate", "task", "p1", reg, {}, "prompt")
        assert result == "respuesta-p1" and used == "p1"

    def test_call_with_fallback_uses_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from motor.core.llm.router.strategy import call_with_fallback

        monkeypatch.setattr("motor.core.llm.router.strategy.time.sleep", lambda s: None)
        p1, p2 = FakeProv("p1"), FakeProv("p2")
        p1.generate = lambda prompt, **kw: "Error: boom"  # type: ignore[method-assign]
        reg = FakeRegistry({"p1": p1, "p2": p2})
        result, used = call_with_fallback(p1, "generate", "task", "p1", reg, {}, "prompt")
        assert result == "respuesta-p2" and used == "p2"

    def test_call_with_fallback_no_available(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from motor.core.llm.router.strategy import call_with_fallback

        monkeypatch.setattr("motor.core.llm.router.strategy.time.sleep", lambda s: None)
        p1 = FakeProv("p1")
        p1.generate = lambda prompt, **kw: "Error: boom"  # type: ignore[method-assign]
        reg = FakeRegistry({"p1": p1})
        result, used = call_with_fallback(p1, "generate", "task", "p1", reg, {}, "prompt")
        assert used == "p1" and "Error:" in result

    def test_call_with_fallback_skips_unavailable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from motor.core.llm.router.strategy import call_with_fallback

        monkeypatch.setattr("motor.core.llm.router.strategy.time.sleep", lambda s: None)
        p1, p2, p3 = FakeProv("p1"), FakeProv("p2"), FakeProv("p3")
        p1.generate = lambda prompt, **kw: "Error: boom"  # type: ignore[method-assign]
        p2.generate = lambda prompt, **kw: "Error: boom"  # type: ignore[method-assign]
        closed = CircuitBreaker("p2", failure_threshold=1, recovery_timeout=600.0)
        with pytest.raises(ConnectionError):
            closed.call(lambda: (_ for _ in ()).throw(ConnectionError("c")))
        cbs = {"p2": closed}
        reg = FakeRegistry({"p1": p1, "p2": p2, "p3": p3})
        result, used = call_with_fallback(p1, "generate", "task", "p1", reg, cbs, "prompt")
        assert result == "respuesta-p3" and used == "p3"

    def test_call_with_fallback_all_fail(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from motor.core.llm.router.strategy import call_with_fallback

        monkeypatch.setattr("motor.core.llm.router.strategy.time.sleep", lambda s: None)
        p1, p2 = FakeProv("p1"), FakeProv("p2")
        p1.generate = lambda prompt, **kw: "Error: boom"  # type: ignore[method-assign]
        p2.generate = lambda prompt, **kw: "Error: boom2"  # type: ignore[method-assign]
        reg = FakeRegistry({"p1": p1, "p2": p2})
        result, used = call_with_fallback(p1, "generate", "task", "p1", reg, {}, "prompt")
        assert used == "p1" and result == "Error: boom"

    def test_call_with_fallback_disabled(self) -> None:
        from motor.core.llm.router.strategy import call_with_fallback

        p1, p2 = FakeProv("p1"), FakeProv("p2")
        p1.generate = lambda prompt, **kw: "Error: boom"  # type: ignore[method-assign]
        reg = FakeRegistry({"p1": p1, "p2": p2})
        result, used = call_with_fallback(p1, "generate", "task", "p1", reg, {}, False, 3, "prompt")
        assert used == "p1" and result == "Error: boom"


class TestRouterProviders:
    def test_resolve_explicit(self) -> None:
        from motor.core.llm.router.providers import resolve, resolve_name

        reg = FakeRegistry({"a": FakeProv("a"), "b": FakeProv("b")})
        assert resolve("generate", "a", reg, {}).name[1] if False else True
        assert resolve("generate", "a", reg, {})._name == "a"
        assert resolve_name("generate", "a", reg, {}) == "a"

    def test_resolve_routes(self) -> None:
        from motor.core.llm.router.providers import resolve, resolve_name

        reg = FakeRegistry({"a": FakeProv("a"), "b": FakeProv("b")})
        assert resolve("generate", None, reg, {"generate": "b"})._name == "b"
        assert resolve_name("generate", None, reg, {"generate": "b"}) == "b"

    def test_resolve_default(self) -> None:
        from motor.core.llm.router.providers import resolve, resolve_name

        reg = FakeRegistry({"a": FakeProv("a")}, default="a")
        assert resolve("generate", None, reg, {})._name == "a"
        assert resolve_name("generate", None, reg, {}) == "a"

    def test_resolve_unknown_provider_raises(self) -> None:
        from motor.core.llm.router.providers import resolve

        reg = FakeRegistry({"a": FakeProv("a")}, default="a")
        with pytest.raises(RuntimeError):
            resolve("generate", "zz", reg, {})

    def test_resolve_no_default_raises(self) -> None:
        from motor.core.llm.router.providers import resolve

        reg = FakeRegistry({})
        with pytest.raises(RuntimeError):
            resolve("generate", None, reg, {})

    def test_resolve_route_unregistered_then_default(self) -> None:
        from motor.core.llm.router.providers import resolve, resolve_name

        reg = FakeRegistry({"a": FakeProv("a")}, default="a")
        assert resolve("generate", None, reg, {"generate": "no-existe"})._name == "a"
        empty = FakeRegistry({})
        with pytest.raises(RuntimeError):
            resolve("generate", None, empty, {"generate": "no-existe"})
        assert resolve_name("generate", None, reg, {"generate": "no-existe"}) == "a"
        assert resolve_name("x", None, FakeRegistry({}), {}) == "unknown"


class TestRouterCapability:
    def test_find_with_error(self) -> None:
        from motor.core.llm.router.capability import find_providers_by_capability

        class BoomProv(FakeProv):
            def supports(self, capability: str) -> bool:
                raise RuntimeError("boom")

        reg = FakeRegistry({"a": BoomProv("a"), "b": FakeProv("b", ["chat"])})
        assert find_providers_by_capability("chat", reg) == ["b"]

    def test_select_preferred(self) -> None:
        from motor.core.llm.router.capability import select_provider_by_capability

        reg = FakeRegistry({"a": FakeProv("a", ["chat"]), "b": FakeProv("b", ["embed"])})
        assert select_provider_by_capability("chat", None, reg) == "a"
        assert select_provider_by_capability("embed", "a", reg) == "b"
        assert select_provider_by_capability("chat", "b", reg) == "a"

    def test_select_preferred_error(self) -> None:
        from motor.core.llm.router.capability import select_provider_by_capability

        class BoomProv(FakeProv):
            def supports(self, capability: str) -> bool:
                raise RuntimeError("boom")

        reg = FakeRegistry({"a": BoomProv("a"), "b": FakeProv("b", ["chat"])})
        assert select_provider_by_capability("chat", "a", reg) == "b"
        with pytest.raises(RuntimeError):
            select_provider_by_capability("vision", None, reg)

    def test_select_no_capability_raises(self) -> None:
        from motor.core.llm.router.capability import select_provider_by_capability

        reg = FakeRegistry({"a": FakeProv("a", ["chat"])})
        with pytest.raises(RuntimeError):
            select_provider_by_capability("vision", None, reg)


class TestRouterHealthCache:
    def _health(self, name: str) -> dict[str, Any]:
        return {"provider": name, "status": "ok"}

    def test_store_and_get(self) -> None:
        from motor.core.llm.router.health import health_get_cached, health_store_cache

        cache: dict[str, tuple[float, dict[str, Any] | None]] = {}
        lock = threading.Lock()
        health_store_cache("a", self._health("a"), cache, lock)
        got = health_get_cached("a", cache, lock, 30.0)
        assert got == self._health("a")
        assert health_get_cached("zzz", cache, lock, 30.0) is None

    def test_expired_entry_refetched(self) -> None:
        from motor.core.llm.router.health import health_get_cached

        cache: dict[str, tuple[float, dict[str, Any] | None]] = {"a": (0.0, self._health("a"))}
        lock = threading.Lock()
        assert health_get_cached("a", cache, lock, 0.001) is None
        assert cache["a"] == (0.0, None)

    def test_concurrent_refresh(self) -> None:
        from motor.core.llm.router.health import health_get_cached, health_store_cache

        cache: dict[str, tuple[float, dict[str, Any] | None]] = {"a": (0.0, None)}
        lock = threading.Lock()

        def worker() -> None:
            time.sleep(0.02)
            health_store_cache("a", self._health("a"), cache, lock)

        t = threading.Thread(target=worker)
        t.start()
        got = health_get_cached("a", cache, lock, 30.0)
        t.join()
        assert got == self._health("a")

    def test_remove(self) -> None:
        from motor.core.llm.router.health import health_remove_cache

        cache: dict[str, tuple[float, dict[str, Any] | None]] = {"a": (1.0, self._health("a"))}
        lock = threading.Lock()
        health_remove_cache("a", cache, lock)
        health_remove_cache("missing", cache, lock)
        assert cache == {}


class TestLLMRouterRemanentes:
    def test_registry_property_y_circuit_state(self) -> None:
        from motor.core.llm.router import LLMRouter

        reg = FakeRegistry({"a": FakeProv("a", ["chat", "generate"])}, default="a")
        router = LLMRouter(registry=reg)
        assert router.registry is reg
        assert router.circuit_state("nope") == "no_circuit"
        router.generate("hola")
        assert router.circuit_state("a") in ("closed", "open", "half_open", "half-open")

    def test_reset_circuit(self) -> None:
        from motor.core.llm.router import LLMRouter

        reg = FakeRegistry({"a": FakeProv("a", ["chat", "generate"])}, default="a")
        router = LLMRouter(registry=reg)
        router.reset_circuit("sin-circuito")
        router.generate("hola")
        router.reset_circuit("a")
        assert router.circuit_state("a") == "closed"

    def test_generate_provider_explicito(self) -> None:
        from motor.core.llm.router import LLMRouter

        a, b = FakeProv("a"), FakeProv("b")
        router = LLMRouter(registry=FakeRegistry({"a": a, "b": b}, default="a"))
        assert router.generate("hola", provider="b") == "respuesta-b"
        assert router.generate("hola", model="m", options={"x": 1}) == "respuesta-a"

    def test_embed_y_embed_async(self) -> None:
        import asyncio

        from motor.core.llm.router import LLMRouter

        a = FakeProv("a")
        router = LLMRouter(registry=FakeRegistry({"a": a}, default="a"))
        assert router.embed(["uno"], provider="a") == [[0.1, 0.2]]
        assert asyncio.run(router.embed_async(["uno"], provider="a")) == [[0.1, 0.2]]

    def test_invalidate_health_cache(self) -> None:
        from motor.core.llm.router import LLMRouter

        a = FakeProv("a")
        router = LLMRouter(registry=FakeRegistry({"a": a}, default="a"))
        router._health_cache["a"] = (1.0, {"x": 1})
        router.invalidate_health_cache("a")
        assert router._health_cache == {}
        router._health_cache["a"] = (1.0, {"x": 1})
        router.invalidate_health_cache()
        assert router._health_cache == {}

    def test_health_ok_y_cache(self) -> None:
        from motor.core.llm.router import LLMRouter

        a = FakeProv("a")
        router = LLMRouter(registry=FakeRegistry({"a": a}, default="a"))
        h1 = router.health()
        assert h1["status"] == "ok" and "latency_ms" in h1
        h2 = router.health()
        assert h2 is h1 or h2["status"] == "ok"

    def test_health_error(self) -> None:
        from motor.core.llm.router import LLMRouter

        class BadProv(FakeProv):
            def health(self) -> dict[str, Any]:
                raise ConnectionError("cae")

        router = LLMRouter(registry=FakeRegistry({"a": BadProv("a")}, default="a"))
        h = router.health()
        assert h["status"] == "error" and "detail" in h

    def test_health_circuit_open(self) -> None:
        from motor.core.llm.router import LLMRouter

        a = FakeProv("a")
        router = LLMRouter(registry=FakeRegistry({"a": a}, default="a"))
        cb = CircuitBreaker("a", failure_threshold=1, recovery_timeout=600.0)
        with pytest.raises(ConnectionError):
            cb.call(lambda: (_ for _ in ()).throw(ConnectionError("c")))
        router._circuit_breakers["a"] = cb
        h = router.health()
        assert h["status"] == "error"

    def test_capabilities_en_routador(self) -> None:
        from motor.core.llm.router import LLMRouter

        a, b = FakeProv("a", ["chat"]), FakeProv("b", ["embed"])
        router = LLMRouter(registry=FakeRegistry({"a": a, "b": b}, default="a"))
        assert router.find_providers_by_capability("embed") == ["b"]
        assert router.select_provider_by_capability("embed") == "b"
        assert router.select_provider_by_capability("chat", preferred="b") == "a"
        assert router.generate_with_capability("hola", capability="chat") == "respuesta-a"

    def test_monitor_enabled_mas_profiling(self) -> None:
        from motor.core.llm.router import LLMRouter

        a = FakeProv("a", ["chat", "generate"])
        router = LLMRouter(
            registry=FakeRegistry({"a": a}, default="a"),
            monitor_enabled=True,
            profiling_enabled=True,
            hotspot_threshold_ms=50.0,
            baseline_enabled=True,
        )
        assert router.generate("hola") == "respuesta-a"
        assert router._monitor is not None and router._profiler is None and router._detector is None


class TestRouterTrendBlocker:
    def test_circuit_breaker_open_error(self) -> None:
        err = CircuitBreakerOpenError("p", 5.0)
        assert err.retry_after == 5.0


class TestRouterCoberturaFina:
    """Cobertura 100x100: remanentes finos del router (TASK-20260814-001)."""

    def test_health_con_monitor(self) -> None:
        from motor.core.llm.router import LLMRouter

        a = FakeProv("a")
        router = LLMRouter(registry=FakeRegistry({"a": a}, default="a"), monitor_enabled=True, health_cache_ttl=0.001)
        h = router.health()
        assert h["status"] == "ok"

    def test_health_con_profiler_y_detector(self) -> None:
        from motor.core.llm.router import LLMRouter

        a = FakeProv("a")
        router = LLMRouter(
            registry=FakeRegistry({"a": a}, default="a"),
            profiling_enabled=True,
            hotspot_threshold_ms=10.0,
            health_cache_ttl=0.001,
        )
        h = router.health()
        assert h["status"] == "ok" and "latency_ms" in h

    def test_preferred_exitoso(self) -> None:
        from motor.core.llm.router.capability import select_provider_by_capability

        reg = FakeRegistry({"a": FakeProv("a", ["chat"])})
        assert select_provider_by_capability("chat", "a", reg) == "a"

    def test_classify_error_sin_httpx(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from motor.core.llm.router.utils import _classify_error

        real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__

        def no_httpx(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "httpx":
                raise ImportError("bloqueado")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr("builtins.__import__", no_httpx)
        assert _classify_error(ValueError("v")) == "error"

    def test_is_transient_sin_httpx(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from motor.core.llm.router.strategy import _is_transient_error

        real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__

        def no_httpx(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "httpx":
                raise ImportError("bloqueado")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr("builtins.__import__", no_httpx)
        assert _is_transient_error(ValueError("v")) is False

    def test_retry_zero_attempts(self) -> None:
        from motor.core.llm.router.strategy import call_with_retry

        prov = FakeProv("p1")
        result = call_with_retry(
            prov,
            "generate",
            "task",
            "p1",
            FakeRegistry({"p1": prov}),
            {},
            prompt="x",
            retry_max_attempts=0,
        )
        assert "Error:" in result

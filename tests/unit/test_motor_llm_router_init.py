"""Tests para motor/core/llm/router/__init__.py — LLMRouter."""
from __future__ import annotations

from unittest import mock

import pytest

from motor.core.llm.router import LLMRouter


class FakeProvider:
    def __init__(self, generate_result="ok", health_result=None):
        self._gen = generate_result
        self._health = health_result or {"status": "ok"}

    def generate(self, prompt, **kwargs):
        if isinstance(self._gen, Exception):
            raise self._gen
        return self._gen

    def embed(self, texts, **kwargs):
        return [[0.1] * 4 for _ in texts]

    async def embed_async(self, texts, **kwargs):
        return [[0.1] * 4 for _ in texts]

    def health(self):
        return dict(self._health)

    def supports(self, capability: str) -> bool:
        return True


class FakeRegistry:
    def __init__(self, providers: dict, default="ollama"):
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


@pytest.fixture
def router() -> LLMRouter:
    reg = FakeRegistry({"ollama": FakeProvider()})
    return LLMRouter(registry=reg)


class TestInit:
    def test_defaults(self) -> None:
        reg = FakeRegistry({"ollama": FakeProvider()})
        r = LLMRouter(registry=reg)
        assert r.registry is reg
        assert r._profiler is None
        assert r._detector is None
        assert r._baseline is None
        assert r._monitor is None

    def test_profiling_enabled(self, monkeypatch) -> None:
        profiler = mock.Mock()
        monkeypatch.setattr("motor.core.llm.profiler.LLMProfiler", mock.Mock(return_value=profiler))
        r = LLMRouter(registry=FakeRegistry({"o": FakeProvider()}), profiling_enabled=True)
        assert r._profiler is profiler

    def test_hotspot_enabled(self, monkeypatch) -> None:
        detector = mock.Mock()
        monkeypatch.setattr("motor.core.llm.detector.HotspotDetector", mock.Mock(return_value=detector))
        r = LLMRouter(registry=FakeRegistry({"o": FakeProvider()}), hotspot_threshold_ms=500.0)
        assert r._detector is detector

    def test_baseline_enabled(self, monkeypatch) -> None:
        baseline = mock.Mock()
        monkeypatch.setattr("motor.core.llm.baseline.PerformanceBaseline", mock.Mock(return_value=baseline))
        r = LLMRouter(registry=FakeRegistry({"o": FakeProvider()}), baseline_enabled=True)
        assert r._baseline is baseline

    def test_monitor_enabled(self, monkeypatch) -> None:
        monitor = mock.Mock()
        monkeypatch.setattr("motor.core.llm.monitor.PerformanceMonitor", mock.Mock(return_value=monitor))
        r = LLMRouter(registry=FakeRegistry({"o": FakeProvider()}), monitor_enabled=True)
        assert r._monitor is monitor
        assert r._profiler is None  # monitor reemplaza profiler/detector/baseline


class TestCircuit:
    def test_circuit_state_sin_cb(self, router: LLMRouter) -> None:
        assert router.circuit_state("nope") == "no_circuit"

    def test_circuit_state_con_cb(self, router: LLMRouter) -> None:
        router.generate("hola")  # crea el cb
        assert router.circuit_state("ollama") != "no_circuit"

    def test_reset_circuit(self, router: LLMRouter) -> None:
        cb = mock.Mock()
        router._circuit_breakers["ollama"] = cb
        router.reset_circuit("ollama")
        cb.reset.assert_called_once()
        router.reset_circuit("inexistente")  # no debe lanzar


class TestGenerate:
    def test_generate_ok(self, router: LLMRouter) -> None:
        assert router.generate("hola") == "ok"

    def test_generate_provider_explicito(self) -> None:
        prov = FakeProvider(generate_result="desde openai")
        r = LLMRouter(registry=FakeRegistry({"ollama": FakeProvider(), "openai": prov}))
        assert r.generate("hola", provider="openai") == "desde openai"

    def test_generate_error(self) -> None:
        prov = FakeProvider(generate_result=ValueError("boom"))
        r = LLMRouter(registry=FakeRegistry({"ollama": prov}), retry_enabled=False)
        result = r.generate("hola")
        assert result.startswith("Error:")


class TestEmbed:
    def test_embed_ok(self, router: LLMRouter) -> None:
        out = router.embed(["hola", "mundo"])
        assert len(out) == 2
        assert len(out[0]) == 4

    @pytest.mark.asyncio
    async def test_embed_async(self, router: LLMRouter) -> None:
        out = await router.embed_async(["hola"])
        assert len(out) == 1


class TestHealth:
    def test_health_ok(self, router: LLMRouter) -> None:
        h = router.health()
        assert h["status"] == "ok"
        assert "latency_ms" in h

    def test_health_cache(self, router: LLMRouter) -> None:
        router.health()
        router.health()
        # cache: segunda llamada sin nueva medicion
        assert "ollama" in router._health_cache

    def test_invalidate_health_cache(self, router: LLMRouter) -> None:
        router._health_cache["ollama"] = (1.0, {"status": "ok"})
        router.invalidate_health_cache("ollama")
        assert "ollama" not in router._health_cache
        router._health_cache["x"] = (1.0, {})
        router.invalidate_health_cache()
        assert router._health_cache == {}

    def test_health_error(self) -> None:
        FakeProvider(health_result=None)

        class FailingProvider(FakeProvider):
            def health(self):
                raise ConnectionError("caido")

        r = LLMRouter(registry=FakeRegistry({"ollama": FailingProvider()}))
        h = r.health()
        assert h["status"] == "error"
        assert "caido" in h["detail"]


class TestCapability:
    def test_find(self, router: LLMRouter) -> None:
        out = router.find_providers_by_capability("chat")
        assert isinstance(out, list)

    def test_select(self, router: LLMRouter) -> None:
        assert router.select_provider_by_capability("chat") == "ollama"

    def test_generate_with_capability(self, router: LLMRouter) -> None:
        assert router.generate_with_capability("pregunta") == "ok"

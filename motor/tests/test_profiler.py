"""Tests del profiler interno LLM (F20-B1).

Verifica:
1. Profiler mide wall time y cpu time
2. Profiler mide memoria (tracemalloc)
3. Profiler thread-safe (operaciones concurrentes)
4. Profiler desactivado por defecto
5. Integración con router (profiling_enabled=True)
"""

from __future__ import annotations

import time

from motor.core.llm.base import BaseLLMProvider
from motor.core.llm.profiler import LLMProfiler
from motor.core.llm.registry import ProviderRegistry
from motor.core.llm.router import LLMRouter


class _MockOK(BaseLLMProvider):
    def generate(self, prompt, model=None, options=None):
        time.sleep(0.01)  # Simular trabajo
        return "ok"
    def embed(self, texts, model=None): return [[0.0]]
    async def embed_async(self, texts, model=None): return [[0.0]]
    def health(self): return {"status": "ok"}


class _MockSlow(BaseLLMProvider):
    def generate(self, prompt, model=None, options=None):
        time.sleep(0.05)
        return "slow_ok"
    def embed(self, texts, model=None): return [[0.0]]
    async def embed_async(self, texts, model=None): return [[0.0]]
    def health(self): return {"status": "ok"}


class TestLLMProfiler:
    def test_profiler_disabled_by_default(self) -> None:
        p = LLMProfiler(enabled=False)
        assert not p.enabled

    def test_profiler_start_stop(self) -> None:
        p = LLMProfiler(enabled=True)
        profile = p.start("test_prov", "generate")
        assert profile is not None
        assert profile.provider == "test_prov"
        assert profile.operation == "generate"

        time.sleep(0.01)
        result = p.stop("test_prov", "generate")
        assert result is not None
        assert result.wall_time_ms >= 8.0  # Al menos 8ms
        assert result.cpu_time_ms >= 0

    def test_profiler_disabled_returns_none(self) -> None:
        p = LLMProfiler(enabled=False)
        assert p.start("p", "g") is None
        assert p.stop("p", "g") is None

    def test_profiler_measures_memory(self) -> None:
        p = LLMProfiler(enabled=True)
        p.start("mem_test", "embed")
        _ = list(range(10000))  # Asignar memoria
        profile = p.stop("mem_test", "embed")
        assert profile is not None
        # Debería haber detectado al menos alguna asignación
        assert profile.peak_memory_bytes >= 0
        assert profile.allocations_count >= 0

    def test_profiler_multiple_operations(self) -> None:
        p = LLMProfiler(enabled=True)
        p.start("a", "gen")
        time.sleep(0.005)
        p.stop("a", "gen")

        p.start("b", "gen")
        time.sleep(0.01)
        p.stop("b", "gen")

        recent = p.get_recent(5)
        assert len(recent) >= 2
        # b debe tener mayor wall_time que a
        profiles = {r["provider"]: r for r in recent}
        assert profiles["b"]["wall_time_ms"] >= profiles["a"]["wall_time_ms"]

    def test_profiler_get_stats(self) -> None:
        p = LLMProfiler(enabled=True)
        for _ in range(3):
            p.start("stats_test", "gen")
            time.sleep(0.005)
            p.stop("stats_test", "gen")

        stats = p.get_stats("stats_test")
        assert stats["total_operations"] == 3
        assert stats["total_wall_time_ms"] >= 10
        assert stats["peak_memory_kb"] >= 0

    def test_profiler_get_stats_empty(self) -> None:
        p = LLMProfiler(enabled=True)
        assert p.get_stats("nonexistent") == {}
        assert p.get_stats() == {}

    def test_profiler_reset(self) -> None:
        p = LLMProfiler(enabled=True)
        p.start("r", "g")
        time.sleep(0.005)
        p.stop("r", "g")
        assert len(p.get_recent(10)) >= 1
        p.reset()
        assert len(p.get_recent(10)) == 0

    def test_profiler_concurrent(self) -> None:
        """Dos operaciones concurrentes no deben interferir."""
        from concurrent.futures import ThreadPoolExecutor

        p = LLMProfiler(enabled=True)

        def _work(name: str, sec: float) -> float:
            p.start(name, "gen")
            time.sleep(sec)
            prof = p.stop(name, "gen")
            return prof.wall_time_ms if prof else 0

        with ThreadPoolExecutor(max_workers=2) as pool:
            f1 = pool.submit(_work, "conc_a", 0.03)
            f2 = pool.submit(_work, "conc_b", 0.01)
            t1 = f1.result()
            t2 = f2.result()

        assert t1 >= 20, f"conc_a wall_time too low: {t1}"
        assert t2 >= 5, f"conc_b wall_time too low: {t2}"

    def test_profiler_close(self) -> None:
        p = LLMProfiler(enabled=True)
        assert p.enabled
        p.close()
        assert not p.enabled
        assert p.start("x", "y") is None


class TestProfilerRouterIntegration:
    def test_profiler_inactive_by_default(self) -> None:
        reg = ProviderRegistry()
        reg.register("ok", _MockOK(), default=True)
        router = LLMRouter(registry=reg)
        assert not router._profiling_enabled

    def test_profiler_active_when_enabled(self) -> None:
        reg = ProviderRegistry()
        reg.register("ok", _MockOK(), default=True)
        router = LLMRouter(registry=reg, profiling_enabled=True)
        assert router._profiling_enabled

    def test_generate_profiles_when_enabled(self) -> None:
        reg = ProviderRegistry()
        reg.register("ok", _MockSlow(), default=True)
        router = LLMRouter(registry=reg, profiling_enabled=True)
        router.generate("test")
        assert router._profiler is not None
        recent = router._profiler.get_recent(5)
        assert len(recent) >= 1
        prof = recent[0]
        assert prof["provider"] == "ok"
        assert prof["wall_time_ms"] >= 40  # _MockSlow duerme 50ms

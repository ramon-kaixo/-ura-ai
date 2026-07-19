"""Tests del sistema de performance baselines (F20-B3).

Verifica:
1. Creación y actualización de baselines
2. Comparación contra baseline
3. Detección de regresiones
4. Ausencia de falsos positivos
5. Thread-safety
6. Persistencia (save/load)
7. Integración con router
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path  # noqa: TC003

from motor.core.llm.base import BaseLLMProvider
from motor.core.llm.baseline import PerformanceBaseline
from motor.core.llm.registry import ProviderRegistry
from motor.core.llm.router import LLMRouter


class _MockProvider(BaseLLMProvider):
    def __init__(self, delay: float = 0.0) -> None:
        self.delay = delay

    def generate(self, prompt, model=None, options=None):
        if self.delay > 0:
            time.sleep(self.delay)
        return "ok"

    def embed(self, texts, model=None):
        return [[0.0]]

    async def embed_async(self, texts, model=None):
        return [[0.0]]

    def health(self):
        return {"status": "ok"}


class TestPerformanceBaseline:
    def test_baseline_create(self) -> None:
        b = PerformanceBaseline(max_samples=10)
        b.record("p1", "gen", wall_time_ms=100, cpu_time_ms=50, peak_memory_bytes=1024)
        stats = b.get_baseline("p1", "gen")
        assert stats is not None
        assert stats.sample_count == 1
        assert stats.wall_time_p50 == 100

    def test_baseline_update(self) -> None:
        b = PerformanceBaseline(max_samples=10)
        for _ in range(5):
            b.record("p", "g", wall_time_ms=100)
        stats = b.get_baseline("p", "g")
        assert stats is not None
        assert stats.sample_count == 5
        assert stats.wall_time_p50 == 100

    def test_baseline_percentiles(self) -> None:
        b = PerformanceBaseline(max_samples=10)
        for i in range(10):
            b.record("p", "g", wall_time_ms=float(i * 10))
        stats = b.get_baseline("p", "g")
        assert stats is not None
        assert 40 <= stats.wall_time_p50 <= 50
        assert stats.wall_time_p95 >= 80
        assert stats.wall_time_p99 >= 80

    def test_baseline_compare_no_regression(self) -> None:
        b = PerformanceBaseline(max_samples=10)
        for _ in range(5):
            b.record("p", "g", wall_time_ms=100)
        regressions = b.compare("p", "g", wall_time_ms=100)
        assert len(regressions) == 0

    def test_baseline_compare_slight_increase(self) -> None:
        """Aumento pequeño (10%) no debe detectar regresión con threshold 1.5x."""
        b = PerformanceBaseline(max_samples=5)
        for _ in range(5):
            b.record("p", "g", wall_time_ms=100)
        regressions = b.compare("p", "g", wall_time_ms=110)
        assert len(regressions) == 0

    def test_baseline_regression_detected(self) -> None:
        b = PerformanceBaseline(max_samples=5)
        for _ in range(5):
            b.record("p", "g", wall_time_ms=100)
        # 3x el valor baseline con threshold 1.5x → regresión
        regressions = b.compare("p", "g", wall_time_ms=300)
        assert len(regressions) >= 1
        r = regressions[0]
        assert r.provider == "p"
        assert r.operation == "g"
        assert r.ratio >= 2.0

    def test_baseline_regression_cpu(self) -> None:
        b = PerformanceBaseline(max_samples=5)
        for _ in range(5):
            b.record("p", "g", wall_time_ms=100, cpu_time_ms=50)
        regressions = b.compare("p", "g", wall_time_ms=100, cpu_time_ms=150)
        assert len(regressions) >= 1
        assert any(r.metric == "cpu_time_p50" for r in regressions)

    def test_baseline_regression_memory(self) -> None:
        b = PerformanceBaseline(max_samples=5)
        for _ in range(5):
            b.record("p", "g", wall_time_ms=100, peak_memory_bytes=1000)
        regressions = b.compare("p", "g", wall_time_ms=100, peak_memory_bytes=5000)
        assert len(regressions) >= 1
        assert any("memory" in r.metric for r in regressions)

    def test_baseline_no_data(self) -> None:
        b = PerformanceBaseline()
        assert b.get_baseline("x", "y") is None
        assert b.compare("x", "y", 100) == []

    def test_baseline_insufficient_samples(self) -> None:
        """Menos de 3 muestras no genera comparación."""
        b = PerformanceBaseline(max_samples=10)
        b.record("p", "g", wall_time_ms=100)
        b.record("p", "g", wall_time_ms=100)
        assert b.compare("p", "g", wall_time_ms=999) == []

    def test_baseline_get_all(self) -> None:
        b = PerformanceBaseline(max_samples=5)
        b.record("a", "gen", 100)
        b.record("b", "embed", 200)
        all_b = b.get_all_baselines()
        assert "a.gen" in all_b
        assert "b.embed" in all_b

    def test_baseline_save_load(self, tmp_path: Path) -> None:
        b = PerformanceBaseline(max_samples=5)
        b.record("p", "g", wall_time_ms=100, cpu_time_ms=50, peak_memory_bytes=1024)
        path = tmp_path / "baseline.json"
        b.save(str(path))

        b2 = PerformanceBaseline(max_samples=5)
        b2.load(str(path))
        stats = b2.get_baseline("p", "g")
        assert stats is not None
        assert stats.wall_time_p50 == 100
        assert stats.cpu_time_p50 == 50

    def test_baseline_save_load_nonexistent(self, tmp_path: Path) -> None:
        b = PerformanceBaseline()
        b.load(str(tmp_path / "nonexistent.json"))  # No debe fallar

    def test_baseline_reset(self) -> None:
        b = PerformanceBaseline(max_samples=5)
        b.record("p", "g", 100)
        assert b.get_baseline("p", "g") is not None
        b.reset()
        assert b.get_baseline("p", "g") is None

    def test_baseline_thread_safe(self) -> None:
        b = PerformanceBaseline(max_samples=100)

        def _record(name: str) -> None:
            for _ in range(20):
                b.record(name, "gen", wall_time_ms=float(100))

        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(_record, f"t{i}") for i in range(4)]
            for f in futures:
                f.result()

        for i in range(4):
            stats = b.get_baseline(f"t{i}", "gen")
            assert stats is not None
            assert stats.sample_count == 20


class TestBaselineRouterIntegration:
    def test_baseline_inactive_by_default(self) -> None:
        reg = ProviderRegistry()
        reg.register("ok", _MockProvider(), default=True)
        router = LLMRouter(registry=reg)
        assert router._baseline is None

    def test_baseline_active_when_enabled(self) -> None:
        reg = ProviderRegistry()
        reg.register("ok", _MockProvider(), default=True)
        router = LLMRouter(registry=reg, profiling_enabled=True, baseline_enabled=True)
        assert router._baseline is not None

    def test_baseline_records_via_router(self) -> None:
        reg = ProviderRegistry()
        reg.register("ok", _MockProvider(delay=0.01), default=True)
        router = LLMRouter(registry=reg, profiling_enabled=True, baseline_enabled=True)
        router.generate("test")
        stats = router._baseline.get_baseline("ok", "generate")
        assert stats is not None
        assert stats.sample_count == 1
        assert stats.wall_time_p50 >= 5

    def test_baseline_multiple_calls(self) -> None:
        reg = ProviderRegistry()
        reg.register("ok", _MockProvider(delay=0.005), default=True)
        router = LLMRouter(registry=reg, profiling_enabled=True, baseline_enabled=True)
        for _ in range(5):
            router.generate("test")
        stats = router._baseline.get_baseline("ok", "generate")
        assert stats is not None
        assert stats.sample_count == 5

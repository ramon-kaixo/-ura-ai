"""Tests del monitor continuo de rendimiento (F20-B4).

Verifica:
1. Colección de datos del monitor
2. Detección de regresiones
3. Detección de hotspots
4. Crecimiento de memoria
5. Límite de historial
6. Reset
7. Thread-safety
8. Integración con router
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

from motor.core.llm.base import BaseLLMProvider
from motor.core.llm.monitor import PerformanceMonitor, PerformanceSnapshot
from motor.core.llm.registry import ProviderRegistry
from motor.core.llm.router import LLMRouter


class _MockDelayed(BaseLLMProvider):
    def __init__(self, delay: float = 0.0) -> None:
        self.delay = delay
    def generate(self, prompt, model=None, options=None):
        if self.delay > 0:
            time.sleep(self.delay)
        return "ok"
    def embed(self, texts, model=None): return [[0.0]]
    async def embed_async(self, texts, model=None): return [[0.0]]
    def health(self): return {"status": "ok"}


class TestPerformanceMonitor:
    def test_monitor_collect(self) -> None:
        m = PerformanceMonitor(hotspot_threshold_ms=9999)
        m.start_operation("p1", "gen")
        time.sleep(0.01)
        snap = m.finish_operation("p1", "gen")
        assert snap is not None
        assert snap.provider == "p1"
        assert snap.operation == "gen"
        assert snap.wall_time_ms >= 5
        assert not snap.is_hotspot  # threshold muy alto

    def test_monitor_no_operation(self) -> None:
        m = PerformanceMonitor()
        snap = m.finish_operation("nonexistent", "gen")
        assert snap is None

    def test_monitor_hotspot(self) -> None:
        m = PerformanceMonitor(hotspot_threshold_ms=10)
        m.start_operation("slow", "gen")
        time.sleep(0.02)
        snap = m.finish_operation("slow", "gen")
        assert snap is not None
        assert snap.is_hotspot
        assert snap.hotspot_record is not None

    def test_monitor_regression(self) -> None:
        m = PerformanceMonitor(hotspot_threshold_ms=9999)
        # Establecer baseline con operaciones rápidas
        for _ in range(5):
            m.start_operation("reg", "gen")
            time.sleep(0.005)
            m.finish_operation("reg", "gen")

        # Operación mucho más lenta
        m.start_operation("reg", "gen")
        time.sleep(0.05)
        snap = m.finish_operation("reg", "gen")
        assert snap is not None
        assert len(snap.regressions) >= 1

    def test_monitor_memory_growth(self) -> None:
        """El monitor registra memoria correctamente."""
        m = PerformanceMonitor(hotspot_threshold_ms=9999)
        m.start_operation("mem", "gen")
        _ = list(range(5000))
        snap = m.finish_operation("mem", "gen")
        assert snap is not None
        assert snap.peak_memory_kb >= 0

    def test_monitor_history_limit(self) -> None:
        m = PerformanceMonitor(hotspot_threshold_ms=9999, history_size=5)
        for i in range(10):
            m.start_operation("p", "gen")
            time.sleep(0.002)
            m.finish_operation("p", "gen")
        history = m.get_history(100)
        assert len(history) == 5  # Limitado a 5
        assert m.get_report()["history_size"] == 5

    def test_monitor_reset(self) -> None:
        m = PerformanceMonitor(hotspot_threshold_ms=9999)
        m.start_operation("p", "g")
        time.sleep(0.005)
        m.finish_operation("p", "g")
        assert len(m.get_history(10)) == 1
        m.reset()
        assert len(m.get_history(10)) == 0
        assert m.get_report()["total_operations"] == 0

    def test_monitor_report(self) -> None:
        m = PerformanceMonitor(hotspot_threshold_ms=10)
        m.start_operation("p", "gen")
        time.sleep(0.02)
        m.finish_operation("p", "gen")
        report = m.get_report()
        assert report["total_operations"] == 1
        assert report["total_hotspots"] == 1
        assert report["hotspot_stats"]["total_hotspots"] == 1

    def test_monitor_get_recent_issues(self) -> None:
        m = PerformanceMonitor(hotspot_threshold_ms=10)
        m.start_operation("p", "gen")
        time.sleep(0.02)
        m.finish_operation("p", "gen")
        issues = m.get_recent_issues(10)
        assert len(issues) >= 1
        assert issues[0]["is_hotspot"]

    def test_monitor_thread_safe(self) -> None:
        m = PerformanceMonitor(hotspot_threshold_ms=9999, history_size=100)

        def _work(name: str) -> None:
            for _ in range(10):
                m.start_operation(name, "gen")
                time.sleep(0.002)
                m.finish_operation(name, "gen")

        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(_work, f"t{i}") for i in range(4)]
            for f in futures:
                f.result()

        report = m.get_report()
        assert report["total_operations"] == 40  # 4 * 10
        assert report["history_size"] <= 100

    def test_snapshot_has_issues(self) -> None:
        snap = PerformanceSnapshot("p", "g", 100, is_hotspot=True)
        assert snap.has_issues()
        snap2 = PerformanceSnapshot("p", "g", 100)
        assert not snap2.has_issues()


class TestMonitorRouterIntegration:
    def test_monitor_inactive_by_default(self) -> None:
        reg = ProviderRegistry()
        reg.register("ok", _MockDelayed(), default=True)
        router = LLMRouter(registry=reg)
        assert router._monitor is None

    def test_monitor_active_when_enabled(self) -> None:
        reg = ProviderRegistry()
        reg.register("ok", _MockDelayed(), default=True)
        router = LLMRouter(registry=reg, monitor_enabled=True)
        assert router._monitor is not None

    def test_monitor_records_via_router(self) -> None:
        reg = ProviderRegistry()
        reg.register("ok", _MockDelayed(delay=0.01), default=True)
        router = LLMRouter(registry=reg, monitor_enabled=True)
        router.generate("test")
        report = router._monitor.get_report()
        assert report["total_operations"] == 1
        assert report["history_size"] >= 1

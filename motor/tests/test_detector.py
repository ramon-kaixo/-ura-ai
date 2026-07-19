"""Tests del detector de hotspots (F20-B2).

Verifica:
1. Detección de operaciones lentas
2. Umbral configurable
3. Detector desactivado por defecto
4. Ranking de hotspots
5. Thread-safety
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

from motor.core.llm.base import BaseLLMProvider
from motor.core.llm.detector import HotspotDetector
from motor.core.llm.profiler import LLMProfiler
from motor.core.llm.registry import ProviderRegistry
from motor.core.llm.router import LLMRouter


class _MockHot(BaseLLMProvider):
    def generate(self, prompt, model=None, options=None):
        time.sleep(0.05)
        return "hot_ok"

    def embed(self, texts, model=None):
        return [[0.0]]

    async def embed_async(self, texts, model=None):
        return [[0.0]]

    def health(self):
        return {"status": "ok"}


class _MockCold(BaseLLMProvider):
    def generate(self, prompt, model=None, options=None):
        return "cold_ok"

    def embed(self, texts, model=None):
        return [[0.0]]

    async def embed_async(self, texts, model=None):
        return [[0.0]]

    def health(self):
        return {"status": "ok"}


class TestHotspotDetector:
    def test_hotspot_detection(self) -> None:
        d = HotspotDetector(threshold_ms=30)
        record = d.evaluate("p", "gen", wall_time_ms=100)
        assert record is not None
        assert record.provider == "p"
        assert record.operation == "gen"
        assert record.wall_time_ms == 100
        assert record.rank == 1

    def test_below_threshold(self) -> None:
        d = HotspotDetector(threshold_ms=100)
        record = d.evaluate("p", "gen", wall_time_ms=50)
        assert record is None

    def test_exact_threshold(self) -> None:
        d = HotspotDetector(threshold_ms=100)
        record = d.evaluate("p", "gen", wall_time_ms=100)
        assert record is not None  # >= threshold

    def test_hotspot_disabled(self) -> None:
        d = HotspotDetector(threshold_ms=0)
        # Con threshold 0, todo evaluado es hotspot
        record = d.evaluate("p", "gen", wall_time_ms=100)
        assert record is not None  # 100 >= 0

    def test_hotspot_threshold_change(self) -> None:
        d = HotspotDetector(threshold_ms=100)
        assert d.evaluate("p", "g", 50) is None
        d.threshold_ms = 30
        assert d.evaluate("p", "g", 50) is not None  # Ahora es hotspot

    def test_hotspot_ranking(self) -> None:
        d = HotspotDetector(threshold_ms=10)
        d.evaluate("slow", "gen", wall_time_ms=200)
        d.evaluate("medium", "gen", wall_time_ms=100)
        d.evaluate("fast", "gen", wall_time_ms=50)

        hotspots = d.get_hotspots(3)
        assert len(hotspots) == 3
        assert hotspots[0]["provider"] == "slow"
        assert hotspots[0]["rank"] == 1
        assert hotspots[1]["provider"] == "medium"
        assert hotspots[1]["rank"] == 2
        assert hotspots[2]["provider"] == "fast"
        assert hotspots[2]["rank"] == 3

    def test_hotspot_ranking_sort_by_memory(self) -> None:
        d = HotspotDetector(threshold_ms=10)
        d.evaluate("a", "gen", wall_time_ms=100, peak_memory_bytes=1000)
        d.evaluate("b", "gen", wall_time_ms=100, peak_memory_bytes=9999)
        d.evaluate("c", "gen", wall_time_ms=100, peak_memory_bytes=500)

        hotspots = d.get_hotspots(3, sort_by="memory")
        assert hotspots[0]["provider"] == "b"  # Mayor memoria

    def test_hotspot_empty(self) -> None:
        d = HotspotDetector(threshold_ms=100)
        assert d.get_hotspots() == []
        assert d.get_stats()["total_hotspots"] == 0

    def test_hotspot_stats(self) -> None:
        d = HotspotDetector(threshold_ms=10)
        d.evaluate("p", "g", wall_time_ms=100)
        d.evaluate("p", "g", wall_time_ms=200)
        stats = d.get_stats()
        assert stats["total_hotspots"] == 2
        assert stats["max_wall_time_ms"] == 200
        assert stats["min_wall_time_ms"] == 100
        assert stats["avg_wall_time_ms"] == 150

    def test_hotspot_reset(self) -> None:
        d = HotspotDetector(threshold_ms=10)
        d.evaluate("p", "g", wall_time_ms=100)
        assert len(d.get_hotspots()) == 1
        d.reset()
        assert len(d.get_hotspots()) == 0

    def test_hotspot_max_records(self) -> None:
        d = HotspotDetector(threshold_ms=10, max_records=3)
        for i in range(5):
            d.evaluate("p", "g", wall_time_ms=float(100 + i))
        hotspots = d.get_hotspots(10)
        assert len(hotspots) == 3  # Solo los últimos 3

    def test_hotspot_thread_safe(self) -> None:
        d = HotspotDetector(threshold_ms=10)

        def _work(name: str) -> None:
            for _ in range(10):
                d.evaluate(name, "gen", wall_time_ms=float(100 + hash(name) % 100))

        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(_work, f"h{i}") for i in range(4)]
            for f in futures:
                f.result()

        hotspots = d.get_hotspots(100)
        assert len(hotspots) <= 40  # 4 workers * 10 = 40 registros
        # Rankings deben ser consistentes
        ranks = [h["rank"] for h in hotspots]
        assert ranks == sorted(ranks)  # 1, 2, 3, ...

    def test_evaluate_from_profile(self) -> None:
        p = LLMProfiler(enabled=True)
        d = HotspotDetector(threshold_ms=10)

        p.start("prov", "gen")
        time.sleep(0.02)
        profile = p.stop("prov", "gen")

        record = d.evaluate_from_profile(profile)
        assert record is not None
        assert record.provider == "prov"
        assert record.wall_time_ms >= 15  # Al menos 15ms

    def test_evaluate_from_profile_none(self) -> None:
        d = HotspotDetector(threshold_ms=10)
        assert d.evaluate_from_profile(None) is None


class TestHotspotRouterIntegration:
    def test_detector_inactive_by_default(self) -> None:
        reg = ProviderRegistry()
        reg.register("ok", _MockCold(), default=True)
        router = LLMRouter(registry=reg)
        assert router._detector is None

    def test_detector_active_with_threshold(self) -> None:
        reg = ProviderRegistry()
        reg.register("ok", _MockCold(), default=True)
        router = LLMRouter(registry=reg, profiling_enabled=True, hotspot_threshold_ms=50)
        assert router._detector is not None
        assert router._detector.threshold_ms == 50

    def test_hotspot_detected_via_router(self) -> None:
        reg = ProviderRegistry()
        reg.register("hot", _MockHot(), default=True)
        router = LLMRouter(registry=reg, profiling_enabled=True, hotspot_threshold_ms=30)
        router.generate("test")
        assert router._detector is not None
        hotspots = router._detector.get_hotspots(5)
        assert len(hotspots) >= 1
        assert hotspots[0]["wall_time_ms"] >= 40  # _MockHot duerme 50ms

    def test_cold_operation_not_hotspot(self) -> None:
        reg = ProviderRegistry()
        reg.register("cold", _MockCold(), default=True)
        router = LLMRouter(registry=reg, profiling_enabled=True, hotspot_threshold_ms=500)
        router.generate("test")
        assert router._detector is not None
        hotspots = router._detector.get_hotspots(5)
        assert len(hotspots) == 0  # No supera el umbral

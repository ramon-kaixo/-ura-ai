"""Tests para el stack de observabilidad LLM.

Cubre: _logging (percentile/log_call), profiler, detector de hotspots,
baseline de rendimiento, PerformanceMonitor, LLMMetrics, ProviderRegistry
y el CircuitBreaker de motor.core.llm.
"""
from __future__ import annotations

import logging
import time
import tracemalloc
from unittest import mock

import pytest

from motor.core.llm._logging import log_call, percentile
from motor.core.llm.baseline import DEFAULT_THRESHOLDS, BaselineStats, PerformanceBaseline, RegressionResult
from motor.core.llm.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError, CircuitState
from motor.core.llm.detector import HotspotDetector, HotspotRecord
from motor.core.llm.monitor import PerformanceMonitor, PerformanceSnapshot
from motor.core.llm.observability import LLMMetrics
from motor.core.llm.profiler import LLMOperationProfile, LLMProfiler
from motor.core.llm.registry import ProviderRegistry

# ===================================================================
# _logging — percentile y log_call
# ===================================================================

class TestPercentile:
    def test_empty_returns_zero(self) -> None:
        assert percentile([], 50) == 0.0

    def test_single_value(self) -> None:
        assert percentile([5.0], 50) == 5.0

    def test_p50(self) -> None:
        assert percentile(list(range(1, 11)), 50) == 6.0

    def test_p0_min(self) -> None:
        assert percentile(list(range(1, 11)), 0) == 1.0

    def test_p100_max(self) -> None:
        assert percentile(list(range(1, 11)), 100) == 10.0

    def test_unsorted_input(self) -> None:
        assert percentile([10, 1, 5], 50) == 5.0


class TestLogCall:
    def test_info_sin_error(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.INFO, logger="motor.core.llm._logging"):
            log_call("ollama", "qwen", 12.5)
        assert "llm_call" in caplog.text
        assert "provider=ollama" in caplog.text
        assert "model=qwen" in caplog.text

    def test_warning_con_error(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.WARNING, logger="motor.core.llm._logging"):
            log_call("ollama", "qwen", 12.5, "timeout")
        assert "error=timeout" in caplog.text

    def test_extra_kwargs(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.INFO, logger="motor.core.llm._logging"):
            log_call("p", "m", 1.0, prompt_tokens=10)
        assert "prompt_tokens=10" in caplog.text


# ===================================================================
# LLMProfiler
# ===================================================================

class TestProfiler:
    def test_start_stop(self) -> None:
        p = LLMProfiler(enabled=True)
        profile = p.start("ollama", "generate", "qwen")
        assert isinstance(profile, LLMOperationProfile)
        assert profile.provider == "ollama"
        assert profile.model == "qwen"
        result = p.stop("ollama", "generate")
        assert result is profile
        assert result.wall_time_ms >= 0.0
        assert result.cpu_time_ms >= 0.0
        assert result.allocations_count >= 0

    def test_stop_sin_start(self) -> None:
        p = LLMProfiler(enabled=True)
        assert p.stop("x", "y") is None

    def test_disabled(self) -> None:
        p = LLMProfiler(enabled=False)
        assert p.enabled is False
        assert p.start("x", "y") is None
        assert p.stop("x", "y") is None

    def test_is_tracing_activo(self) -> None:
        p = LLMProfiler(enabled=True)
        assert p.is_tracing is True

    def test_profile_to_dict(self) -> None:
        profile = LLMOperationProfile("p", "op", "m")
        profile.wall_time_ms = 100.0
        d = profile.to_dict()
        assert d["provider"] == "p"
        assert d["wall_time_ms"] == 100.0
        assert d["peak_memory_kb"] == 0.0

    def test_profile_repr(self) -> None:
        profile = LLMOperationProfile("p", "op")
        assert "LLMOperationProfile" in repr(profile)

    def test_get_recent(self) -> None:
        p = LLMProfiler(enabled=True)
        p.start("a", "op1")
        p.stop("a", "op1")
        p.start("a", "op2")
        p.stop("a", "op2")
        recent = p.get_recent(1)
        assert len(recent) == 1
        assert recent[0]["operation"] == "op2"

    def test_get_stats(self) -> None:
        p = LLMProfiler(enabled=True)
        p.start("a", "op")
        p.stop("a", "op")
        stats = p.get_stats("a")
        assert stats["total_operations"] == 1
        assert "total_wall_time_ms" in stats
        assert p.get_stats("other") == {}

    def test_get_stats_sin_datos(self) -> None:
        p = LLMProfiler(enabled=True)
        assert p.get_stats() == {}

    def test_reset(self) -> None:
        p = LLMProfiler(enabled=True)
        p.start("a", "op")
        p.stop("a", "op")
        p.reset()
        assert p.get_stats() == {}
        assert p.get_recent() == []

    def test_close(self) -> None:
        p = LLMProfiler(enabled=True)
        p.close()
        assert p.enabled is False
        assert tracemalloc.is_tracing() is False
        p.close()

    def test_singleton_desactivado(self) -> None:
        from motor.core.llm.profiler import profiler

        assert profiler.enabled is False


# ===================================================================
# HotspotDetector
# ===================================================================

class TestHotspotDetector:
    def test_threshold_property(self) -> None:
        d = HotspotDetector(threshold_ms=2000.0)
        assert d.threshold_ms == 2000.0
        d.threshold_ms = 100.0
        assert d.threshold_ms == 100.0

    def test_evaluate_under_threshold(self) -> None:
        d = HotspotDetector(threshold_ms=100.0)
        assert d.evaluate("p", "op", wall_time_ms=50.0) is None

    def test_evaluate_over_threshold(self) -> None:
        d = HotspotDetector(threshold_ms=100.0)
        rec = d.evaluate("p", "op", wall_time_ms=500.0, cpu_time_ms=10.0)
        assert isinstance(rec, HotspotRecord)
        assert rec.rank == 1
        assert rec.to_dict()["wall_time_ms"] == 500.0
        assert "Hotspot" in repr(rec)

    def test_ranking_desc(self) -> None:
        d = HotspotDetector(threshold_ms=1.0)
        d.evaluate("p", "a", wall_time_ms=100.0)
        d.evaluate("p", "b", wall_time_ms=400.0)
        d.evaluate("p", "c", wall_time_ms=200.0)
        assert d.get_hotspots(3)[0]["operation"] == "b"
        assert [r["rank"] for r in d.get_hotspots(3)] == [1, 2, 3]

    def test_max_records_trim(self) -> None:
        d = HotspotDetector(threshold_ms=1.0, max_records=2)
        for i in range(3):
            d.evaluate("p", f"op{i}", wall_time_ms=100.0 + i)
        assert len(d.get_hotspots(10)) == 2

    def test_evaluate_from_profile_none(self) -> None:
        d = HotspotDetector(threshold_ms=1.0)
        assert d.evaluate_from_profile(None) is None

    def test_evaluate_from_profile(self) -> None:
        d = HotspotDetector(threshold_ms=1.0)
        profile = mock.Mock()
        profile.provider = "p"
        profile.operation = "op"
        profile.wall_time_ms = 500.0
        profile.cpu_time_ms = 10.0
        profile.peak_memory_bytes = 1024
        profile.allocations_count = 3
        rec = d.evaluate_from_profile(profile)
        assert rec is not None
        assert rec.operation == "op"
        assert rec.peak_memory_bytes == 1024

    @pytest.mark.parametrize("sort_by", ["wall_time", "cpu_time", "memory", "otro"])
    def test_get_hotspots_sort_by(self, sort_by: str) -> None:
        d = HotspotDetector(threshold_ms=1.0)
        d.evaluate("p", "wall", wall_time_ms=100.0, cpu_time_ms=5.0, peak_memory_bytes=10)
        d.evaluate("p", "cpu", wall_time_ms=50.0, cpu_time_ms=20.0, peak_memory_bytes=10)
        out = d.get_hotspots(10, sort_by=sort_by)
        assert len(out) == 2

    def test_get_hotspots_empty(self) -> None:
        d = HotspotDetector(threshold_ms=1.0)
        assert d.get_hotspots() == []

    def test_get_stats_empty(self) -> None:
        d = HotspotDetector(threshold_ms=100.0)
        assert d.get_stats() == {"total_hotspots": 0, "threshold_ms": 100.0}

    def test_get_stats_filled(self) -> None:
        d = HotspotDetector(threshold_ms=1.0)
        d.evaluate("ollama", "gen", wall_time_ms=100.0)
        d.evaluate("gemini", "gen", wall_time_ms=50.0)
        stats = d.get_stats()
        assert stats["total_hotspots"] == 2
        assert set(stats["providers"]) == {"ollama", "gemini"}
        assert stats["min_wall_time_ms"] == 50.0
        assert stats["max_wall_time_ms"] == 100.0

    def test_reset(self) -> None:
        d = HotspotDetector(threshold_ms=1.0)
        d.evaluate("p", "op", wall_time_ms=100.0)
        d.reset()
        assert d.get_stats() == {"total_hotspots": 0, "threshold_ms": 1.0}


# ===================================================================
# PerformanceBaseline
# ===================================================================

class TestBaseline:
    def test_record_y_compute(self) -> None:
        b = PerformanceBaseline()
        b.record("p", "op", wall_time_ms=100.0)
        b.record("p", "op", wall_time_ms=200.0)
        stats = b.get_baseline("p", "op")
        assert stats is not None
        assert stats.sample_count == 2
        assert stats.wall_time_p50 > 0
        assert stats.throughput > 0

    def test_get_baseline_missing(self) -> None:
        b = PerformanceBaseline()
        assert b.get_baseline("p", "op") is None

    def test_compare_con_pocas_muestras(self) -> None:
        b = PerformanceBaseline()
        b.record("p", "op", wall_time_ms=100.0)
        b.record("p", "op", wall_time_ms=100.0)
        assert b.compare("p", "op", wall_time_ms=900.0) == []

    def test_compare_detecta_regresion(self) -> None:
        b = PerformanceBaseline()
        for _ in range(4):
            b.record("p", "op", wall_time_ms=100.0)
        regressions = b.compare("p", "op", wall_time_ms=500.0)
        assert len(regressions) >= 1
        assert regressions[0].metric == "wall_time_p50"
        assert regressions[0].ratio >= 1.5

    def test_compare_sin_regresion(self) -> None:
        b = PerformanceBaseline()
        for _ in range(4):
            b.record("p", "op", wall_time_ms=100.0)
        assert b.compare("p", "op", wall_time_ms=110.0) == []

    def test_thresholds_personalizados(self) -> None:
        b = PerformanceBaseline(thresholds={"wall_time_p50": 1.1})
        for _ in range(4):
            b.record("p", "op", wall_time_ms=100.0)
        assert len(b.compare("p", "op", wall_time_ms=150.0)) >= 1

    def test_regression_ratio_zero_baseline(self) -> None:
        r = RegressionResult("p", "op", "wall_time_p50", 0.0, 5.0, 2.0)
        assert r.ratio == 999.0
        assert "wall_time_p50" in repr(r)
        d = r.to_dict()
        assert d["ratio"] == 999.0
        assert d["baseline_value"] == 0.0

    def test_baseline_stats_from_dict(self) -> None:
        stats = BaselineStats({"wall_time_p50": 10.0, "sample_count": 5})
        assert stats.wall_time_p50 == 10.0
        assert stats.sample_count == 5
        d = stats.to_dict()
        assert d["wall_time_p50"] == 10.0

    def test_baseline_stats_defaults(self) -> None:
        stats = BaselineStats()
        assert stats.wall_time_p50 == 0.0
        assert stats.sample_count == 0

    def test_max_samples_trim(self) -> None:
        b = PerformanceBaseline(max_samples=2)
        for i in range(5):
            b.record("p", "op", wall_time_ms=float(i))
        stats = b.get_baseline("p", "op")
        assert stats is not None
        assert stats.sample_count == 2
        assert stats.wall_time_p50 == 4.0

    def test_get_all_baselines(self) -> None:
        b = PerformanceBaseline()
        b.record("p", "op", wall_time_ms=100.0)
        all_b = b.get_all_baselines()
        assert "p.op" in all_b

    def test_save_y_load(self, tmp_path: pytest.TempPathFactory) -> None:
        b = PerformanceBaseline()
        b.record("p", "op", wall_time_ms=100.0)
        path = tmp_path / "baseline.json"
        b.save(path)
        b2 = PerformanceBaseline()
        b2.load(path)
        stats = b2.get_baseline("p", "op")
        assert stats is not None
        assert stats.sample_count == 1

    def test_load_missing_file(self, tmp_path: pytest.TempPathFactory) -> None:
        b = PerformanceBaseline()
        b.load(tmp_path / "no-existe.json")

    def test_reset(self) -> None:
        b = PerformanceBaseline()
        b.record("p", "op", wall_time_ms=100.0)
        b.reset()
        assert b.get_baseline("p", "op") is None
        assert b.get_all_baselines() == {}

    def test_recompute_sin_muestras(self) -> None:
        b = PerformanceBaseline()
        b.record("p", "op", wall_time_ms=100.0)
        b._recompute(("p", "op"))
        assert b.get_baseline("p", "op") is not None
        b._recompute(("sin", "muestras"))
        assert b.get_baseline("sin", "muestras") is None

    def test_default_thresholds(self) -> None:
        assert DEFAULT_THRESHOLDS["wall_time_p50"] == 1.5


# ===================================================================
# PerformanceMonitor
# ===================================================================

class TestMonitor:
    def _monitor(self, threshold_ms: float = 1.0, history_size: int = 100) -> PerformanceMonitor:
        return PerformanceMonitor(hotspot_threshold_ms=threshold_ms, history_size=history_size)

    def test_start_finish(self) -> None:
        m = self._monitor()
        m.start_operation("ollama", "generate", "qwen")
        snap = m.finish_operation("ollama", "generate")
        assert snap is not None
        assert isinstance(snap, PerformanceSnapshot)
        assert snap.provider == "ollama"
        assert snap.operation == "generate"
        assert snap.to_dict()["provider"] == "ollama"
        assert m._total_operations == 1

    def test_finish_sin_start(self) -> None:
        m = self._monitor()
        assert m.finish_operation("ollama", "generate") is None

    def test_hotspot_detectado(self) -> None:
        m = self._monitor(threshold_ms=1.0)
        m.start_operation("p", "op")
        # Lentitud real (antes dependía de la latencia artificial de
        # tracemalloc.take_snapshot, eliminada en TASK-20260813-006).
        time.sleep(0.005)
        snap = m.finish_operation("p", "op")
        assert snap is not None
        assert snap.is_hotspot is True
        assert snap.has_issues() is True
        assert m._total_hotspots == 1
        assert m.get_report()["total_hotspots"] == 1

    def test_sin_hotspot(self) -> None:
        m = self._monitor(threshold_ms=10_000.0)
        m.start_operation("p", "op")
        snap = m.finish_operation("p", "op")
        assert snap is not None
        assert snap.is_hotspot is False
        assert snap.has_issues() is False

    def test_regresion_en_snapshot(self) -> None:
        m = self._monitor()
        fake = [RegressionResult("p", "op", "wall_time_p50", 100.0, 500.0, 2.0)]
        with mock.patch.object(m._baseline, "compare", return_value=fake):
            m.start_operation("p", "op")
            snap = m.finish_operation("p", "op")
        assert snap is not None
        assert snap.regressions == fake
        assert snap.has_issues() is True
        assert m._total_regressions == 1

    def test_history_trim(self) -> None:
        m = self._monitor(history_size=2)
        for op in ("a", "b", "c"):
            m.start_operation("p", op)
            m.finish_operation("p", op)
        assert len(m._history) == 2
        assert m._history[-1].operation == "c"

    def test_get_history_filters(self) -> None:
        m = self._monitor(threshold_ms=10_000.0)
        for op in ("ok1", "ok2"):
            m.start_operation("p", op)
            m.finish_operation("p", op)
        all_items = m.get_history(n=50)
        assert len(all_items) == 2
        assert m.get_history(only_issues=True) == []
        assert m.get_recent_issues() == []

    def test_get_report_shape(self) -> None:
        m = self._monitor()
        m.start_operation("p", "op")
        m.finish_operation("p", "op")
        report = m.get_report()
        assert report["total_operations"] == 1
        assert "throughput_ops_per_sec" in report
        assert "hotspot_stats" in report
        assert "baselines" in report
        assert report["history_size"] == 1

    def test_properties(self) -> None:
        m = self._monitor()
        assert m.profiler.enabled is True
        assert m.detector.threshold_ms == 1.0
        assert m.baseline is not None

    def test_reset(self) -> None:
        m = self._monitor()
        m.start_operation("p", "op")
        m.finish_operation("p", "op")
        m.reset()
        assert m._total_operations == 0
        assert m._history == []
        assert m.get_report()["total_operations"] == 0


# ===================================================================
# LLMMetrics
# ===================================================================

class TestLLMMetrics:
    def test_record_success(self) -> None:
        m = LLMMetrics()
        m.record("ollama", "generate", 12.5, success=True, tokens=100)
        stats = m.get_stats("ollama", "generate")
        key = "ollama.generate"
        assert stats[key]["llamadas_totales"] == 1
        assert stats[key]["latencia_max_ms"] == 12.5
        assert stats[key]["latencia_media_ms"] == 12.5
        assert stats[key]["tokens_por_segundo"] > 0

    def test_record_failure_con_error(self) -> None:
        m = LLMMetrics()
        m.record("gemini", "generate", 5.0, success=False, error="timeout")
        stats = m.get_stats()
        assert stats["gemini.generate"]["errores"] == {"timeout": 1}

    def test_record_failure_sin_error(self) -> None:
        m = LLMMetrics()
        m.record("p", "op", 1.0, success=False)
        stats = m.get_stats()
        assert stats["p.op"]["errores"] == {}

    def test_max_records_trim(self) -> None:
        m = LLMMetrics()
        for i in range(1001):
            m.record("p", "op", float(i), success=True)
        stats = m.get_stats()
        assert stats["p.op"]["llamadas_totales"] == 1000

    def test_tokens_max_records_trim(self) -> None:
        m = LLMMetrics()
        for i in range(1001):
            m.record("p", "op", 1.0, success=True, tokens=i)
        stats = m.get_stats()
        assert stats["p.op"]["tokens_medios_por_call"] > 0

    def test_filtro_por_provider(self) -> None:
        m = LLMMetrics()
        m.record("a", "op1", 1.0, success=True)
        m.record("b", "op1", 2.0, success=True)
        stats = m.get_stats(provider="a")
        assert list(stats) == ["a.op1"]

    def test_filtro_por_operation(self) -> None:
        m = LLMMetrics()
        m.record("a", "op1", 1.0, success=True)
        m.record("a", "op2", 2.0, success=True)
        stats = m.get_stats(operation="op2")
        assert list(stats) == ["a.op2"]

    def test_sin_datos(self) -> None:
        m = LLMMetrics()
        assert m.get_stats() == {"error": "no data"}

    def test_summary(self) -> None:
        m = LLMMetrics()
        m.record("a", "op1", 1.0, success=True)
        m.record("a", "op2", 2.0, success=False, error="e")
        s = m.summary()
        assert s["a"] == {"total": 2, "ok": 1, "fail": 1}

    def test_summary_vacio(self) -> None:
        m = LLMMetrics()
        assert m.summary() == {}

    def test_reset(self) -> None:
        m = LLMMetrics()
        m.record("a", "op", 1.0, success=True)
        m.reset()
        assert m.get_stats() == {"error": "no data"}


# ===================================================================
# ProviderRegistry
# ===================================================================

class TestProviderRegistry:
    def test_register_default_primer(self) -> None:
        r = ProviderRegistry()
        assert r.default is None
        assert r.default_name is None
        p1 = mock.Mock()
        p2 = mock.Mock()
        r.register("a", p1)
        r.register("b", p2)
        assert r.default is p1
        assert r.default_name == "a"
        assert "a" in r
        assert len(r) == 2

    def test_register_default_explicito(self) -> None:
        r = ProviderRegistry()
        r.register("a", mock.Mock())
        r.register("b", mock.Mock(), default=True)
        assert r.default_name == "b"

    def test_get(self) -> None:
        r = ProviderRegistry()
        p = mock.Mock()
        r.register("a", p)
        assert r.get("a") is p

    def test_get_missing_keyerror(self) -> None:
        r = ProviderRegistry()
        with pytest.raises(KeyError):
            r.get("no-existe")

    def test_unregister_default_fallback(self) -> None:
        r = ProviderRegistry()
        p1, p2 = mock.Mock(), mock.Mock()
        r.register("a", p1)
        r.register("b", p2)
        r.unregister("a")
        assert r.default is p2
        assert "a" not in r
        assert len(r) == 1

    def test_unregister_ultimo(self) -> None:
        r = ProviderRegistry()
        r.register("a", mock.Mock())
        r.unregister("a")
        assert r.default is None
        assert r.default_name is None

    def test_unregister_inexistente(self) -> None:
        r = ProviderRegistry()
        r.register("a", mock.Mock())
        r.unregister("zzz")
        assert r.default_name == "a"

    def test_list(self) -> None:
        r = ProviderRegistry()
        r.register("a", mock.Mock())
        listing = r.list()
        assert "a" in listing


# ===================================================================
# CircuitBreaker (wrapper de motor.core.llm)
# ===================================================================

class TestCircuitBreakerWrapper:
    def test_call_disponible(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=1)
        assert cb.call(lambda: 42) == 42

    def test_call_abre_y_lanza_error(self) -> None:
        cb = CircuitBreaker("test", failure_threshold=1)
        with pytest.raises(RuntimeError):
            cb.call(lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        assert cb.state == CircuitState.OPEN
        with pytest.raises(CircuitBreakerOpenError):
            cb.call(lambda: 42)

    def test_open_error_atributos(self) -> None:
        err = CircuitBreakerOpenError("test", 30.0)
        assert err.provider == "test"
        assert err.retry_after == 30.0

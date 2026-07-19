"""Monitor continuo de rendimiento.

Consolida profiler, hotspot detector y performance baseline.
Detecta automáticamente:
  - regresiones de rendimiento
  - hotspots persistentes
  - incremento de memoria
  - degradación de throughput

Thread-safe. Historial circular configurable.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from motor.core.llm.baseline import PerformanceBaseline, RegressionResult
from motor.core.llm.detector import HotspotDetector, HotspotRecord
from motor.core.llm.profiler import LLMProfiler

log = logging.getLogger(__name__)


class PerformanceSnapshot:
    """Instantánea de rendimiento para una operación."""

    __slots__ = (
        "cpu_time_ms",
        "hotspot_record",
        "is_hotspot",
        "operation",
        "peak_memory_kb",
        "provider",
        "regressions",
        "timestamp",
        "wall_time_ms",
    )

    def __init__(
        self,
        provider: str,
        operation: str,
        wall_time_ms: float,
        cpu_time_ms: float = 0.0,
        peak_memory_kb: float = 0.0,
        is_hotspot: bool = False,  # noqa: FBT001, FBT002
        regressions: list[RegressionResult] | None = None,
        hotspot_record: HotspotRecord | None = None,
    ) -> None:
        self.timestamp = time.monotonic()
        self.provider = provider
        self.operation = operation
        self.wall_time_ms = wall_time_ms
        self.cpu_time_ms = cpu_time_ms
        self.peak_memory_kb = peak_memory_kb
        self.is_hotspot = is_hotspot
        self.regressions = regressions or []
        self.hotspot_record = hotspot_record

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "operation": self.operation,
            "wall_time_ms": round(self.wall_time_ms, 1),
            "cpu_time_ms": round(self.cpu_time_ms, 1),
            "peak_memory_kb": round(self.peak_memory_kb, 1),
            "is_hotspot": self.is_hotspot,
            "regressions": [r.to_dict() for r in self.regressions],
        }

    def has_issues(self) -> bool:
        return self.is_hotspot or len(self.regressions) > 0


class PerformanceMonitor:
    """Monitor continuo de rendimiento.

    Consolida profiler + detector + baseline en una única interfaz.
    """

    def __init__(
        self,
        hotspot_threshold_ms: float = 2000.0,
        baseline_max_samples: int = 100,
        history_size: int = 1000,
    ) -> None:
        self._profiler = LLMProfiler(enabled=True)
        self._detector = HotspotDetector(threshold_ms=hotspot_threshold_ms)
        self._baseline = PerformanceBaseline(max_samples=baseline_max_samples)
        self._history: list[PerformanceSnapshot] = []
        self._max_history = history_size
        self._lock = threading.Lock()
        self._total_operations = 0
        self._total_hotspots = 0
        self._total_regressions = 0

    @property
    def profiler(self) -> LLMProfiler:
        return self._profiler

    @property
    def detector(self) -> HotspotDetector:
        return self._detector

    @property
    def baseline(self) -> PerformanceBaseline:
        return self._baseline

    def start_operation(
        self,
        provider: str,
        operation: str,
        model: str | None = None,
    ) -> Any | None:
        """Inicia medición para una operación. Retorna perfil en curso."""
        return self._profiler.start(provider, operation, model)

    def finish_operation(
        self,
        provider: str,
        operation: str,
    ) -> PerformanceSnapshot | None:
        """Finaliza medición, evalúa hotspot y regresiones.

        Retorna un PerformanceSnapshot con los hallazgos.
        """
        profile = self._profiler.stop(provider, operation)
        if profile is None:
            return None

        wall_ms = profile.wall_time_ms
        cpu_ms = profile.cpu_time_ms
        mem_kb = profile.peak_memory_bytes / 1024

        # Evaluar hotspot
        hotspot_rec = self._detector.evaluate(
            provider,
            operation,
            wall_time_ms=wall_ms,
            cpu_time_ms=cpu_ms,
            peak_memory_bytes=profile.peak_memory_bytes,
            allocations_count=profile.allocations_count,
        )

        # Comparar contra baseline
        regressions = self._baseline.compare(
            provider,
            operation,
            wall_time_ms=wall_ms,
            cpu_time_ms=cpu_ms,
            peak_memory_bytes=profile.peak_memory_bytes,
        )

        # Registrar en baseline (después de comparar para no contaminar)
        self._baseline.record(
            provider,
            operation,
            wall_time_ms=wall_ms,
            cpu_time_ms=cpu_ms,
            peak_memory_bytes=profile.peak_memory_bytes,
        )

        snapshot = PerformanceSnapshot(
            provider=provider,
            operation=operation,
            wall_time_ms=wall_ms,
            cpu_time_ms=cpu_ms,
            peak_memory_kb=mem_kb,
            is_hotspot=hotspot_rec is not None,
            regressions=regressions,
            hotspot_record=hotspot_rec,
        )

        with self._lock:
            self._total_operations += 1
            if snapshot.is_hotspot:
                self._total_hotspots += 1
            if snapshot.regressions:
                self._total_regressions += 1
            self._history.append(snapshot)
            if len(self._history) > self._max_history:
                self._history.pop(0)

        if snapshot.has_issues():
            if snapshot.is_hotspot:
                log.warning(
                    "perf_hotspot  provider=%s op=%s wall=%.0fms",
                    provider,
                    operation,
                    wall_ms,
                )
            for r in regressions:
                log.warning(
                    "perf_regression  provider=%s op=%s metric=%s ratio=%.1fx",
                    provider,
                    operation,
                    r.metric,
                    r.ratio,
                )

        return snapshot

    def get_history(
        self,
        n: int = 50,
        only_issues: bool = False,  # noqa: FBT001, FBT002
    ) -> list[dict[str, Any]]:
        """Historial de operaciones."""
        with self._lock:
            results = list(self._history)
        if only_issues:
            results = [s for s in results if s.has_issues()]
        return [s.to_dict() for s in results[-n:]]

    def get_report(self) -> dict[str, Any]:
        """Informe completo de rendimiento."""
        with self._lock:
            recent = list(self._history)
            issues = [s for s in recent if s.has_issues()]

        hotspot_stats = self._detector.get_stats()
        baseline_info = self._baseline.get_all_baselines()

        # Throughput
        elapsed = max(1.0, time.monotonic() - 1.0)
        throughput = self._total_operations / elapsed

        return {
            "total_operations": self._total_operations,
            "total_hotspots": self._total_hotspots,
            "total_regressions": self._total_regressions,
            "hotspot_ratio": round(
                self._total_hotspots / max(1, self._total_operations),
                3,
            ),
            "regression_ratio": round(
                self._total_regressions / max(1, self._total_operations),
                3,
            ),
            "throughput_ops_per_sec": round(throughput, 1),
            "history_size": len(recent),
            "issues_in_history": len(issues),
            "hotspot_stats": hotspot_stats,
            "baselines": baseline_info,
        }

    def get_recent_issues(self, n: int = 20) -> list[dict[str, Any]]:
        """Últimas N operaciones con problemas."""
        return self.get_history(n=n, only_issues=True)

    def reset(self) -> None:
        with self._lock:
            self._profiler.reset()
            self._detector.reset()
            self._baseline.reset()
            self._history.clear()
            self._total_operations = 0
            self._total_hotspots = 0
            self._total_regressions = 0

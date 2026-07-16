"""Líneas base de rendimiento para detectar regresiones.

Por operación/proveedor almacena:
  - wall time P50/P95/P99
  - cpu time P50/P95/P99
  - memoria pico P50/P95/P99
  - throughput

Permite comparar ejecución actual contra baseline y detectar regresiones.
"""

from __future__ import annotations

import json
import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

# Umbrales de regresión por defecto (multiplicador sobre baseline)
DEFAULT_THRESHOLDS: dict[str, float] = {
    "wall_time_p50": 1.5,
    "wall_time_p95": 2.0,
    "wall_time_p99": 3.0,
    "cpu_time_p50": 2.0,
    "peak_memory_kb_p50": 2.0,
}


def _percentile(data: list[float], p: float) -> float:
    if not data:
        return 0.0
    idx = max(0, min(len(data) - 1, int(len(data) * p / 100)))
    return sorted(data)[idx]


class BaselineStats:
    """Estadísticas de baseline para una operación/proveedor."""

    __slots__ = (
        "cpu_time_p50",
        "cpu_time_p95",
        "cpu_time_p99",
        "peak_memory_kb_p50",
        "peak_memory_kb_p95",
        "peak_memory_kb_p99",
        "sample_count",
        "throughput",
        "wall_time_p50",
        "wall_time_p95",
        "wall_time_p99",
    )

    def __init__(self, data: dict[str, Any] | None = None) -> None:
        if data:
            for k, v in data.items():
                if k in self.__slots__:
                    setattr(self, k, v)
        else:
            self.wall_time_p50: float = 0.0
            self.wall_time_p95: float = 0.0
            self.wall_time_p99: float = 0.0
            self.cpu_time_p50: float = 0.0
            self.cpu_time_p95: float = 0.0
            self.cpu_time_p99: float = 0.0
            self.peak_memory_kb_p50: float = 0.0
            self.peak_memory_kb_p95: float = 0.0
            self.peak_memory_kb_p99: float = 0.0
            self.throughput: float = 0.0
            self.sample_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {s: getattr(self, s, 0.0) for s in self.__slots__}


class RegressionResult:
    """Resultado de una comparación contra baseline."""

    __slots__ = (
        "baseline_value",
        "current_value",
        "metric",
        "operation",
        "provider",
        "ratio",
        "threshold",
    )

    def __init__(
        self,
        provider: str,
        operation: str,
        metric: str,
        baseline_value: float,
        current_value: float,
        threshold: float,
    ) -> None:
        self.provider = provider
        self.operation = operation
        self.metric = metric
        self.baseline_value = baseline_value
        self.current_value = current_value
        self.ratio = current_value / baseline_value if baseline_value > 0 else 999.0
        self.threshold = threshold

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "operation": self.operation,
            "metric": self.metric,
            "baseline_value": round(self.baseline_value, 1),
            "current_value": round(self.current_value, 1),
            "ratio": round(self.ratio, 2),
            "threshold": self.threshold,
        }

    def __repr__(self) -> str:
        return (
            f"Regression(provider={self.provider!r}, op={self.operation!r}, "
            f"metric={self.metric}, ratio={self.ratio:.2f}x "
            f"(threshold={self.threshold:.1f}x))"
        )


class PerformanceBaseline:
    """Línea base de rendimiento por operación/proveedor.

    Thread-safe. Almacena ventanas de muestras y percentiles.
    """

    def __init__(
        self,
        max_samples: int = 100,
        thresholds: dict[str, float] | None = None,
    ) -> None:
        self._max_samples = max_samples
        self._thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
        self._lock = threading.Lock()

        # Muestras crudas: key=(provider, operation) -> list[dict]
        self._samples: dict[tuple[str, str], list[dict[str, float]]] = defaultdict(list)

        # Baselines computados: key=(provider, operation) -> BaselineStats
        self._baselines: dict[tuple[str, str], BaselineStats] = {}

    def record(
        self,
        provider: str,
        operation: str,
        wall_time_ms: float,
        cpu_time_ms: float = 0.0,
        peak_memory_bytes: int = 0,
    ) -> None:
        """Registra una muestra y actualiza la baseline."""
        key = (provider, operation)
        sample = {
            "wall_time_ms": wall_time_ms,
            "cpu_time_ms": cpu_time_ms,
            "peak_memory_kb": peak_memory_bytes / 1024,
        }

        with self._lock:
            samples = self._samples[key]
            samples.append(sample)
            if len(samples) > self._max_samples:
                samples.pop(0)
            self._recompute(key)

    def _recompute(self, key: tuple[str, str]) -> None:
        samples = self._samples.get(key, [])
        if not samples:
            self._baselines.pop(key, None)
            return

        wall_times = [s["wall_time_ms"] for s in samples]
        cpu_times = [s["cpu_time_ms"] for s in samples]
        mem_kb = [s["peak_memory_kb"] for s in samples]
        elapsed = max(1.0, time.monotonic() - 1.0)  # aprox

        stats = BaselineStats()
        stats.wall_time_p50 = _percentile(wall_times, 50)
        stats.wall_time_p95 = _percentile(wall_times, 95)
        stats.wall_time_p99 = _percentile(wall_times, 99)
        stats.cpu_time_p50 = _percentile(cpu_times, 50)
        stats.cpu_time_p95 = _percentile(cpu_times, 95)
        stats.cpu_time_p99 = _percentile(cpu_times, 99)
        stats.peak_memory_kb_p50 = _percentile(mem_kb, 50)
        stats.peak_memory_kb_p95 = _percentile(mem_kb, 95)
        stats.peak_memory_kb_p99 = _percentile(mem_kb, 99)
        stats.throughput = len(samples) / elapsed
        stats.sample_count = len(samples)

        self._baselines[key] = stats

    def get_baseline(self, provider: str, operation: str) -> BaselineStats | None:
        """Retorna la baseline para una operación/proveedor."""
        with self._lock:
            return self._baselines.get((provider, operation))

    def compare(
        self,
        provider: str,
        operation: str,
        wall_time_ms: float,
        cpu_time_ms: float = 0.0,
        peak_memory_bytes: int = 0,
    ) -> list[RegressionResult]:
        """Compara una medición contra la baseline almacenada.

        Retorna lista de regresiones detectadas (vacía = sin regresión).
        """
        baseline = self.get_baseline(provider, operation)
        if baseline is None or baseline.sample_count < 3:
            return []

        regressions: list[RegressionResult] = []
        checks: list[tuple[str, float, float]] = [
            ("wall_time_p50", wall_time_ms, baseline.wall_time_p50),
            ("wall_time_p95", wall_time_ms, baseline.wall_time_p95),
            ("wall_time_p99", wall_time_ms, baseline.wall_time_p99),
            ("cpu_time_p50", cpu_time_ms, baseline.cpu_time_p50),
            ("peak_memory_kb_p50", peak_memory_bytes / 1024, baseline.peak_memory_kb_p50),
        ]

        for metric, current, expected in checks:
            if expected <= 0:
                continue
            threshold = self._thresholds.get(metric, 2.0)
            min_abs = max(expected * 0.3, 2.0)
            if current > expected * threshold and current > expected + min_abs:
                regressions.append(RegressionResult(
                    provider=provider,
                    operation=operation,
                    metric=metric,
                    baseline_value=expected,
                    current_value=current,
                    threshold=threshold,
                ))

        return regressions

    def get_all_baselines(self) -> dict[str, Any]:
        """Todas las baselines como dict."""
        with self._lock:
            return {
                f"{k[0]}.{k[1]}": v.to_dict()
                for k, v in self._baselines.items()
            }

    def save(self, path: str | Path) -> None:
        """Persiste baselines a JSON."""
        data = self.get_all_baselines()
        Path(path).write_text(json.dumps(data, indent=2) + "\n")

    def load(self, path: str | Path) -> None:
        """Carga baselines desde JSON."""
        p = Path(path)
        if not p.exists():
            return
        data = json.loads(p.read_text())
        with self._lock:
            for key_str, values in data.items():
                provider, operation = key_str.split(".", 1)
                stats = BaselineStats(values)
                self._baselines[(provider, operation)] = stats

    def reset(self) -> None:
        with self._lock:
            self._samples.clear()
            self._baselines.clear()

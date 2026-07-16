from __future__ import annotations

import logging
import threading
import time
from typing import Any

log = logging.getLogger("ura.observability.metrics")


class Counter:
    def __init__(self, name: str, description: str = "", labels: dict[str, str] | None = None) -> None:
        self.name = name
        self.description = description
        self._labels = dict(labels or {})
        self._value = 0
        self._lock = threading.Lock()

    def inc(self, amount: int = 1) -> None:
        with self._lock:
            self._value += amount

    def get(self) -> int:
        with self._lock:
            return self._value

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "type": "counter",
                "name": self.name,
                "description": self.description,
                "value": self._value,
                "labels": dict(self._labels),
            }


class Gauge:
    def __init__(self, name: str, description: str = "", labels: dict[str, str] | None = None) -> None:
        self.name = name
        self.description = description
        self._labels = dict(labels or {})
        self._value = 0.0
        self._lock = threading.Lock()

    def set(self, value: float) -> None:
        with self._lock:
            self._value = value

    def inc(self, amount: float = 1.0) -> None:
        with self._lock:
            self._value += amount

    def dec(self, amount: float = 1.0) -> None:
        with self._lock:
            self._value -= amount

    def get(self) -> float:
        with self._lock:
            return self._value

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "type": "gauge",
                "name": self.name,
                "description": self.description,
                "value": self._value,
                "labels": dict(self._labels),
            }


class Histogram:
    def __init__(self, name: str, description: str = "", buckets: list[float] | None = None) -> None:
        self.name = name
        self.description = description
        self._buckets = sorted(buckets or [0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1, 5, 10])
        self._counts: dict[str, int] = {str(b): 0 for b in self._buckets}
        self._counts["+Inf"] = 0
        self._sum = 0.0
        self._count = 0
        self._lock = threading.Lock()

    def observe(self, value: float) -> None:
        with self._lock:
            self._count += 1
            self._sum += value
            for b in self._buckets:
                if value <= b:
                    self._counts[str(b)] += 1
            self._counts["+Inf"] += 1

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "type": "histogram",
                "name": self.name,
                "description": self.description,
                "count": self._count,
                "sum": round(self._sum, 3),
                "buckets": {str(k): v for k, v in self._counts.items()},
            }


class Timer:
    def __init__(self, name: str, description: str = "") -> None:
        self.name = name
        self.description = description
        self._histogram = Histogram(name, description)

    def time(self) -> _TimerContext:
        return _TimerContext(self._histogram)

    def record(self, seconds: float) -> None:
        self._histogram.observe(seconds)

    def snapshot(self) -> dict[str, Any]:
        return self._histogram.snapshot()


class _TimerContext:
    def __init__(self, histogram: Histogram) -> None:
        self._histogram = histogram
        self._start = 0.0

    def __enter__(self) -> _TimerContext:  # noqa: PYI034
        self._start = time.monotonic()
        return self

    def __exit__(self, *args: object) -> None:
        elapsed = time.monotonic() - self._start
        self._histogram.observe(elapsed)


class MetricsRegistry:
    def __init__(self) -> None:
        self._counters: dict[str, Counter] = {}
        self._gauges: dict[str, Gauge] = {}
        self._histograms: dict[str, Histogram] = {}
        self._timers: dict[str, Timer] = {}
        self._lock = threading.Lock()

    def counter(self, name: str, description: str = "", labels: dict[str, str] | None = None) -> Counter:
        with self._lock:
            if name not in self._counters:
                self._counters[name] = Counter(name, description, labels)
            return self._counters[name]

    def gauge(self, name: str, description: str = "", labels: dict[str, str] | None = None) -> Gauge:
        with self._lock:
            if name not in self._gauges:
                self._gauges[name] = Gauge(name, description, labels)
            return self._gauges[name]

    def histogram(self, name: str, description: str = "", buckets: list[float] | None = None) -> Histogram:
        with self._lock:
            if name not in self._histograms:
                self._histograms[name] = Histogram(name, description, buckets)
            return self._histograms[name]

    def timer(self, name: str, description: str = "") -> Timer:
        with self._lock:
            if name not in self._timers:
                self._timers[name] = Timer(name, description)
            return self._timers[name]

    def snapshot(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        with self._lock:
            result["counters"] = [c.snapshot() for c in self._counters.values()]
            result["gauges"] = [g.snapshot() for g in self._gauges.values()]
            result["histograms"] = [h.snapshot() for h in self._histograms.values()]
            result["timers"] = [t.snapshot() for t in self._timers.values()]
        return result

#!/usr/bin/env python3
"""Soak Test (OBS-5) — test prolongado con datos sintéticos variados.

Usage:
    python3 scripts/soak_test.py [--duration 3600] [--rate 10]
    python3 scripts/soak_test.py --quick  # 60s quick smoke test

Mide:
- Latencia p50/p95/p99 por subsistema
- Throughput
- Tasa de error
- Estabilidad de trazas (trace_id único por operación)
- Crecimiento de memoria
"""

from __future__ import annotations

import argparse
import os
import random
import sys
import threading
import time

# Add project root to path if running directly
sys.path.insert(0, Path(os.path.dirname(Path(__file__).resolve().parent)))  # noqa: F821, PTH120

from typing import TYPE_CHECKING

from motor.platform.health import HealthAggregator
from motor.platform.tracing import MetricsCollector, TraceExporter

if TYPE_CHECKING:
    from collections.abc import Callable


class Scenario:
    """A single scenario that generates synthetic load."""

    def __init__(
        self,
        name: str,
        fn: Callable[[], None],
        weight: float = 1.0,
    ) -> None:
        self.name = name
        self.fn = fn
        self.weight = weight


def simulate_fusion(collector: MetricsCollector) -> None:
    """Simulate F24→F25 fusion pipeline."""
    for _ in range(random.randint(1, 5)):  # noqa: S311
        start = time.monotonic_ns()
        time.sleep(random.uniform(0.001, 0.01))  # noqa: S311
        error = random.random() < 0.02  # noqa: S311
        duration = time.monotonic_ns() - start
        collector.record("f24→f25", duration, error=error)


def simulate_memory(collector: MetricsCollector) -> None:
    """Simulate F25→F26 memory append."""
    for _ in range(random.randint(1, 3)):  # noqa: S311
        start = time.monotonic_ns()
        time.sleep(random.uniform(0.0005, 0.005))  # noqa: S311
        error = random.random() < 0.01  # noqa: S311
        duration = time.monotonic_ns() - start
        collector.record("f25→f26", duration, error=error)


def simulate_agents(collector: MetricsCollector) -> None:
    """Simulate F26→F27 agent execution."""
    start = time.monotonic_ns()
    time.sleep(random.uniform(0.01, 0.1))  # noqa: S311
    error = random.random() < 0.05  # noqa: S311
    duration = time.monotonic_ns() - start
    collector.record("f26→f27", duration, error=error)


def simulate_protocol(collector: MetricsCollector) -> None:
    """Simulate F27→F28 protocol transport."""
    for _ in range(random.randint(1, 3)):  # noqa: S311
        start = time.monotonic_ns()
        time.sleep(random.uniform(0.0001, 0.001))  # noqa: S311
        duration = time.monotonic_ns() - start
        collector.record("f27→f28", duration)


def health_check(agg: HealthAggregator) -> dict:
    """Run a full health check across simulated subsystems."""
    return agg.health()


class SoakTester:
    """Orchestrates the soak test."""

    def __init__(
        self,
        duration_seconds: int = 3600,
        rate_per_second: int = 10,
        trace_path: str = "",
    ) -> None:
        self.duration = duration_seconds
        self.rate = rate_per_second
        self.collector = MetricsCollector()
        self.health_agg = HealthAggregator()
        self.exporter = TraceExporter(path=trace_path or "soak_traces.jsonl", batch_size=50)
        self.running = False
        self.total_ops = 0
        self.total_errors = 0
        self.start_time = 0.0

        # Register health probes
        self.health_agg.register_health(
            "fusion",
            lambda: {
                "service": "fusion",
                "status": "ok",
                "ops": self.total_ops,
            },
        )
        self.health_agg.register_health(
            "memory",
            lambda: {
                "service": "memory",
                "status": "ok",
                "entries": self.total_ops,
            },
        )

        # Scenarios with weights
        self.scenarios = [
            Scenario("fusion", lambda: simulate_fusion(self.collector), weight=0.3),
            Scenario("memory", lambda: simulate_memory(self.collector), weight=0.3),
            Scenario("agents", lambda: simulate_agents(self.collector), weight=0.2),
            Scenario("protocol", lambda: simulate_protocol(self.collector), weight=0.2),
        ]
        total_weight = sum(s.weight for s in self.scenarios)
        for s in self.scenarios:
            s.weight /= total_weight

    def _pick_scenario(self) -> Scenario:
        r = random.random()  # noqa: S311
        cumulative = 0.0
        for s in self.scenarios:
            cumulative += s.weight
            if r <= cumulative:
                return s
        return self.scenarios[-1]

    def _worker(self) -> None:
        """Single worker thread — runs scenarios."""
        while self.running:
            scenario = self._pick_scenario()
            try:
                scenario.fn()
                with self.collector._lock:
                    self.total_ops += 1
            except Exception:
                with self.collector._lock:
                    self.total_errors += 1
            # Emit a trace event for each operation
            try:
                from motor.platform.tracing import SpanEvent

                ev = SpanEvent(
                    trace_id=f"soak-{self.total_ops}",
                    span_id=f"s{self.total_ops}",
                    parent_span_id="ROOT",
                    source=scenario.name,
                    destination=scenario.name,
                    message_type=scenario.name,
                    message_kind="command",
                    timestamp_utc=time.time(),
                    monotonic_ts=time.monotonic_ns(),
                    duration_ns=0,
                    tags={"soak": "true"},
                )
                self.exporter.emit(ev)
            except Exception:  # noqa: S110
                pass

    def run(self) -> dict:
        """Run the soak test for the configured duration.

        Returns summary dict with metrics.
        """
        self.running = True
        self.start_time = time.time()
        deadline = self.start_time + self.duration

        # Start workers
        num_workers = max(1, self.rate // 5)
        workers = []
        for _ in range(num_workers):
            t = threading.Thread(target=self._worker, daemon=True)
            t.start()
            workers.append(t)

        # Monitor loop
        check_interval = max(1, self.duration // 20)
        last_check = time.time()

        while time.time() < deadline:
            time.sleep(1)

            # Periodic health check
            if time.time() - last_check >= check_interval:
                last_check = time.time()
                elapsed = time.time() - self.start_time
                snap = self.collector.snapshot()

                # Check for metric anomalies
                for stats in snap.values():
                    if stats["count"] > 0 and stats["p99_ms"] > 5000:
                        pass

        # Stop
        self.running = False
        for t in workers:
            t.join(timeout=5)

        self.exporter.flush()
        elapsed = time.time() - self.start_time
        snap = self.collector.snapshot()
        throughput = self.total_ops / max(elapsed, 1)

        return {
            "duration_seconds": elapsed,
            "total_operations": self.total_ops,
            "total_errors": self.total_errors,
            "error_rate": self.total_errors / max(self.total_ops, 1),
            "throughput_ops_per_second": throughput,
            "subsystems": snap,
            "health": self.health_agg.health(),
        }


def print_report(result: dict) -> None:
    """Print a human-readable test report."""
    for _ss, _stats in sorted(result["subsystems"].items()):
        pass
    result["health"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Soak Test (OBS-5)")
    parser.add_argument("--duration", type=int, default=3600, help="Duration in seconds (default: 3600)")
    parser.add_argument("--rate", type=int, default=10, help="Target operations per second (default: 10)")
    parser.add_argument("--quick", action="store_true", help="Quick 60s smoke test")
    parser.add_argument("--output", default="", help="Path for trace output JSONL")
    args = parser.parse_args()

    duration = 60 if args.quick else args.duration
    rate = 5 if args.quick else args.rate

    tester = SoakTester(duration_seconds=duration, rate_per_second=rate, trace_path=args.output)
    result = tester.run()
    print_report(result)

    # Check critical thresholds
    issues = []
    for ss, stats in result["subsystems"].items():
        if stats["count"] > 0 and stats["p99_ms"] > 5000:
            issues.append(f"  ⚠ {ss}: p99={stats['p99_ms']:.0f}ms > 5s")

    if result["error_rate"] > 0.10:
        issues.append(f"  ❌ Error rate {result['error_rate'] * 100:.1f}% > 10% threshold")

    if issues:
        for _issue in issues:
            pass
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()

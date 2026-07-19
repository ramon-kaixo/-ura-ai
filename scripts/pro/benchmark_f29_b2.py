#!/usr/bin/env python3
"""F29 B2 — Validación Técnica: benchmarks de throughput, latencia y memoria.

Mide:
  F26 Memory: append(), state_at(), snapshot throughput
  F27 Scheduler: submit() throughput
  F28 Protocol: serialize/deserialize throughput

Uso:
  python3 scripts/pro/benchmark_f29_b2.py [--output resultados.json]
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import asdict, dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


@dataclass
class BenchmarkResult:
    name: str
    ops: int
    total_s: float
    ops_per_s: float
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    rss_mb: float = 0.0


def benchmark_f26_memory() -> list[BenchmarkResult]:
    """Benchmark F26 Memory: append, state_at, snapshot."""
    results: list[BenchmarkResult] = []

    try:
        from motor.memory import Memory, MemoryEntry, MemoryTimeline
    except ImportError:
        print("[SKIP] F26 Memory no disponible")
        return results

    N = 5000
    memory = Memory()
    timeline = MemoryTimeline()

    # Memory.append
    latencies = []
    start = time.time()
    for i in range(N):
        t0 = time.monotonic()
        entry = MemoryEntry(
            entry_id=f"bench_{i}",
            timestamp=time.time(),
            source="benchmark",
        )
        memory.append(entry)
        timeline.append(entry)
        latencies.append((time.monotonic() - t0) * 1000)
    total = time.time() - start
    sorted_lats = sorted(latencies)
    results.append(
        BenchmarkResult(
            name="F26 Memory.append",
            ops=N,
            total_s=round(total, 3),
            ops_per_s=round(N / total, 1),
            p50_ms=round(sorted_lats[N // 2], 3),
            p95_ms=round(sorted_lats[int(N * 0.95)], 3),
            p99_ms=round(sorted_lats[int(N * 0.99)], 3),
        )
    )

    # Memory.state_at (only if available)
    if hasattr(memory, "state_at"):
        latencies = []
        ts = time.time()
        start = time.time()
        for _ in range(N):
            t0 = time.monotonic()
            memory.state_at(ts)
            latencies.append((time.monotonic() - t0) * 1000)
        total = time.time() - start
        sorted_lats = sorted(latencies)
        results.append(
            BenchmarkResult(
                name="F26 Memory.state_at",
                ops=N,
                total_s=round(total, 3),
                ops_per_s=round(N / total, 1),
                p50_ms=round(sorted_lats[N // 2], 3),
                p95_ms=round(sorted_lats[int(N * 0.95)], 3),
                p99_ms=round(sorted_lats[int(N * 0.99)], 3),
            )
        )

    return results


def benchmark_f27_scheduler() -> list[BenchmarkResult]:
    """Benchmark F27 Scheduler: submit throughput."""
    results: list[BenchmarkResult] = []

    try:
        from motor.agents.models import (
            AgentCapability,
            AgentExecution,
            AgentPolicy,
            AgentTask,
        )
        from motor.agents.scheduler import AgentScheduler
    except ImportError:
        print("[SKIP] F27 Scheduler no disponible")
        return results

    scheduler = AgentScheduler()
    N = 2000

    latencies = []
    start = time.time()
    for i in range(N):
        t0 = time.monotonic()
        task = AgentTask(task_id=f"bench_{i}", objective=f"Benchmark task {i}")
        execution = AgentExecution(
            agent_id=f"agent_{i}",
            task=task,
            capabilities={AgentCapability.MEMORY_READ},
            policy=AgentPolicy(),
        )
        scheduler.submit(execution)
        latencies.append((time.monotonic() - t0) * 1000)
    total = time.time() - start
    sorted_lats = sorted(latencies)
    results.append(
        BenchmarkResult(
            name="F27 Scheduler.submit",
            ops=N,
            total_s=round(total, 3),
            ops_per_s=round(N / total, 1),
            p50_ms=round(sorted_lats[N // 2], 3),
            p95_ms=round(sorted_lats[int(N * 0.95)], 3),
            p99_ms=round(sorted_lats[int(N * 0.99)], 3),
        )
    )

    scheduler.shutdown(timeout=5)
    return results


def benchmark_f28_protocol() -> list[BenchmarkResult]:
    """Benchmark F28 Protocol: serialize/deserialize throughput."""
    results: list[BenchmarkResult] = []

    try:
        from motor.platform.models import (
            CausationId,
            CorrelationId,
            DeliveryHeader,
            MessageKind,
            ProtocolEnvelope,
            RoutingHeader,
            SpanId,
            TraceHeader,
            TraceId,
            VersionHeader,
        )
        from motor.platform.serializer import (
            JsonProtocolDeserializer,
            JsonProtocolSerializer,
            make_envelope_with_checksum,
            make_message_id,
        )
    except ImportError:
        print("[SKIP] F28 Protocol no disponible")
        return results

    serializer = JsonProtocolSerializer()
    deserializer = JsonProtocolDeserializer()
    N = 10000

    # Build a realistic envelope
    payload = b'{"tool_name": "search", "params": {"q": "hello world"}}'
    env = make_envelope_with_checksum(
        version=VersionHeader(),
        routing=RoutingHeader(
            message_id=make_message_id("1.0", "1.0", "a", "b", "ToolRequest", payload),
            message_type="ToolRequest",
            message_kind=MessageKind.COMMAND,
            source="test",
            destination="bench",
        ),
        trace=TraceHeader(
            trace_id=TraceId("abcdef1234567890"),
            span_id=SpanId("abcdef1234567890"),
            correlation_id=CorrelationId("corr1"),
            causation_id=CausationId.root(),
        ),
        delivery=DeliveryHeader(timeout_ms=5000),
        payload=payload,
    )

    # Serialize
    latencies = []
    start = time.time()
    for _ in range(N):
        t0 = time.monotonic()
        serializer.serialize(env)
        latencies.append((time.monotonic() - t0) * 1000)
    total = time.time() - start
    sorted_lats = sorted(latencies)
    results.append(
        BenchmarkResult(
            name="F28 Protocol.serialize",
            ops=N,
            total_s=round(total, 3),
            ops_per_s=round(N / total, 1),
            p50_ms=round(sorted_lats[N // 2], 6),
            p95_ms=round(sorted_lats[int(N * 0.95)], 6),
            p99_ms=round(sorted_lats[int(N * 0.99)], 6),
        )
    )

    # Deserialize (with checksum verification)
    raw = serializer.serialize(env)
    latencies = []
    start = time.time()
    for _ in range(N):
        t0 = time.monotonic()
        deserializer.deserialize(raw)
        latencies.append((time.monotonic() - t0) * 1000)
    total = time.time() - start
    sorted_lats = sorted(latencies)
    results.append(
        BenchmarkResult(
            name="F28 Protocol.deserialize",
            ops=N,
            total_s=round(total, 3),
            ops_per_s=round(N / total, 1),
            p50_ms=round(sorted_lats[N // 2], 6),
            p95_ms=round(sorted_lats[int(N * 0.95)], 6),
            p99_ms=round(sorted_lats[int(N * 0.99)], 6),
        )
    )

    return results


def main() -> None:
    output = sys.argv[1] if len(sys.argv) > 1 else ""
    import tracemalloc

    tracemalloc.start()

    all_results: list[dict] = []

    for bench_fn in [benchmark_f26_memory, benchmark_f27_scheduler, benchmark_f28_protocol]:
        try:
            results = bench_fn()
            for r in results:
                d = asdict(r)
                print(f"  {r.name:40s} {r.ops_per_s:>10.1f} ops/s  p50={r.p50_ms}ms")
                all_results.append(d)
        except Exception as e:
            print(f"  [ERROR] {bench_fn.__name__}: {e}")

    snapshot = tracemalloc.take_snapshot()
    stats = snapshot.statistics("lineno")
    top = stats[0] if stats else None

    report = {
        "benchmark": "F29 B2 — Validación Técnica",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "results": all_results,
        "peak_memory": {"file": str(top.traceback) if top else "N/A", "size": top.size if top else 0},
    }

    print(json.dumps(report, indent=2))

    if output:
        with open(output, "w") as f:
            json.dump(report, f, indent=2)
        print(f"Resultados guardados en {output}")


if __name__ == "__main__":
    main()

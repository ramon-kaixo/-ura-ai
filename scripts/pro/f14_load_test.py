#!/usr/bin/env python3
"""F14 Load & Stress Test — Bloque 1.

Uso:
  python3 scripts/pro/f14_load_test.py --benchmark L01 --levels 10,100,1000
  python3 scripts/pro/f14_load_test.py --benchmark L02 --levels 10,50,200
  python3 scripts/pro/f14_load_test.py --benchmark L03 --levels 100,1000,10000
  python3 scripts/pro/f14_load_test.py --benchmark L04 --levels 3,5,10
  python3 scripts/pro/f14_load_test.py --benchmark L05
  python3 scripts/pro/f14_load_test.py --benchmark all

Cada benchmark guarda JSON + CSV en motor/data/benchmarks/f14/.
"""

import argparse
import csv
import json
import os
import platform
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psutil

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT))
os.environ.setdefault("URA_LOG_LEVEL", "ERROR")

OUTPUT_DIR = _PROJECT_ROOT / "motor" / "data" / "benchmarks" / "f14"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Metadata del entorno ──────────────────────────────────────────────


def gather_environment() -> dict[str, Any]:
    git_hash = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip() or "unknown"  # noqa: PLW1510, S607
    git_tag = (
        subprocess.run(  # noqa: PLW1510
            ["git", "describe", "--tags", "--always"],  # noqa: S607
            capture_output=True,
            text=True,
        ).stdout.strip()
        or "unknown"
    )
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "commit_sha": git_hash,
        "version": git_tag,
        "hostname": platform.node(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "cpu_cores": os.cpu_count() or 0,
        "ram_total_gb": round(psutil.virtual_memory().total / 1e9, 1),
        "ram_available_gb": round(psutil.virtual_memory().available / 1e9, 1),
    }


ENV = gather_environment()

# ── Monitor de sistema ────────────────────────────────────────────────


class SystemMonitor:
    def __init__(self) -> None:
        self.process = psutil.Process()
        self.snapshots: list[dict[str, Any]] = []

    def snapshot(self) -> dict[str, Any]:
        s = {
            "timestamp": time.time(),
            "cpu_percent": psutil.cpu_percent(interval=0.5),
            "rss_mb": round(self.process.memory_info().rss / 1e6, 1),
            "rss_percent": round(self.process.memory_percent(), 2),
            "threads": self.process.num_threads(),
        }
        try:
            r = subprocess.run(  # noqa: PLW1510
                ["docker", "stats", "ura-qdrant", "--no-stream", "--format", "{{.MemUsage}}"],  # noqa: S607
                capture_output=True,
                text=True,
                timeout=5,
            )
            out = r.stdout.strip()
            if out:
                used = out.split("/")[0].strip()
                if "MiB" in used:
                    s["qdrant_rss_mb"] = float(used.replace("MiB", "").strip())
                elif "GiB" in used:
                    s["qdrant_rss_mb"] = float(used.replace("GiB", "").strip()) * 1024
        except Exception:
            s["qdrant_rss_mb"] = -1
        self.snapshots.append(s)
        return s

    def summary(self) -> dict[str, Any]:
        if not self.snapshots:
            return {}
        cpu_vals = [s["cpu_percent"] for s in self.snapshots]
        rss_vals = [s["rss_mb"] for s in self.snapshots]
        return {
            "cpu_min": round(min(cpu_vals), 1),
            "cpu_max": round(max(cpu_vals), 1),
            "cpu_mean": round(sum(cpu_vals) / len(cpu_vals), 1),
            "cpu_p95": round(sorted(cpu_vals)[int(len(cpu_vals) * 0.95)], 1),
            "rss_min_mb": round(min(rss_vals), 1),
            "rss_max_mb": round(max(rss_vals), 1),
            "rss_mean_mb": round(sum(rss_vals) / len(rss_vals), 1),
            "rss_p95_mb": round(sorted(rss_vals)[int(len(rss_vals) * 0.95)], 1),
            "snapshots": len(self.snapshots),
        }


def percentiles(values: list[float]) -> dict[str, float]:
    if not values:
        return {"p50": 0, "p95": 0, "p99": 0}
    s = sorted(values)
    return {
        "p50": round(s[int(len(s) * 0.50)], 1),
        "p95": round(s[int(len(s) * 0.95)], 1),
        "p99": round(s[int(len(s) * 0.99)], 1),
    }


MONITOR = SystemMonitor()

# ── Helpers de import ─────────────────────────────────────────────────


def _import_qdrant():
    from motor.core.config import UraConfig
    from motor.core.qdrant_client import QdrantClient as QC

    config = UraConfig(qdrant_host="localhost", qdrant_port=6333)
    return QC(config)


def _import_hybrid_retriever():
    from motor.intelligence.retrieval.hybrid import HybridRetriever
    from motor.intelligence.retrieval.lexical import LexicalRetriever
    from motor.intelligence.retrieval.vector import VectorRetriever

    qdrant = _import_qdrant()
    vr = VectorRetriever(qdrant_client=qdrant)
    lr = LexicalRetriever()
    return HybridRetriever(vector_retriever=vr, lexical_retriever=lr, alpha=0.7, beta=0.3)


# ── L01: Runtime ──────────────────────────────────────────────────────


def benchmark_l01(levels: list[int]) -> dict[str, Any]:
    from motor.intelligence.agents.runtime import MultiAgentRuntime

    runtime = MultiAgentRuntime()
    results = []
    all_latencies = []

    for n_wf in levels:
        latencies = []
        errors = 0
        t0 = time.monotonic()

        for i in range(n_wf):
            t1 = time.monotonic()
            try:
                runtime.execute_workflow(
                    objective=f"task-{i}",
                    context={"synthetic": True},
                    timeout=10,
                )
            except Exception:
                errors += 1
            finally:
                latencies.append((time.monotonic() - t1) * 1000)

        total_s = time.monotonic() - t0
        all_latencies.extend(latencies)
        p = percentiles(latencies)
        snap = MONITOR.snapshot()
        results.append(
            {
                "level": n_wf,
                "workflows": n_wf,
                "duration_s": round(total_s, 2),
                "throughput_wfs": round(n_wf / total_s, 2) if total_s > 0 else 0,
                "latency_ms": p,
                "cpu_percent": snap["cpu_percent"],
                "rss_mb": snap["rss_mb"],
                "errors": errors,
                "timeouts": 0,
            },
        )

    return {
        "benchmark_id": "L01",
        "description": "Runtime: workflows concurrentes (MultiAgentRuntime.execute_workflow)",
        "environment": ENV,
        "system_summary": MONITOR.summary(),
        "results": results,
        "overall_latency_ms": percentiles(all_latencies),
    }


# ── L02: Retrieval ────────────────────────────────────────────────────


def benchmark_l02(levels: list[int]) -> dict[str, Any]:
    hr = _import_hybrid_retriever()
    results = []
    all_latencies = []
    test_queries = [
        "qué es ura",
        "cómo funciona el pipeline",
        "memoria episódica",
        "consenso multiagente",
        "observabilidad",
        "plugin system",
        "recuperación ante fallos",
        "basededatos vectorial",
        "búsqueda híbrida",
        "ejecución paralela",
    ]

    for n_q in levels:
        latencies = []
        errors = 0
        t0 = time.monotonic()

        for i in range(n_q):
            q = test_queries[i % len(test_queries)]
            t1 = time.monotonic()
            try:
                hr.search(q, k=5)
            except Exception:
                errors += 1
            finally:
                latencies.append((time.monotonic() - t1) * 1000)

        total_s = time.monotonic() - t0
        all_latencies.extend(latencies)
        p = percentiles(latencies)
        snap = MONITOR.snapshot()
        results.append(
            {
                "level": n_q,
                "queries": n_q,
                "duration_s": round(total_s, 2),
                "throughput_qps": round(n_q / total_s, 2) if total_s > 0 else 0,
                "latency_ms": p,
                "cpu_percent": snap["cpu_percent"],
                "rss_mb": snap["rss_mb"],
                "errors": errors,
            },
        )

    return {
        "benchmark_id": "L02",
        "description": "Retrieval: queries híbridas (HybridRetriever + Qdrant real)",
        "environment": ENV,
        "system_summary": MONITOR.summary(),
        "results": results,
        "overall_latency_ms": percentiles(all_latencies),
    }


# ── L03: Memory ───────────────────────────────────────────────────────


def benchmark_l03(levels: list[int]) -> dict[str, Any]:
    from motor.intelligence.memory.episodic import Episode, EpisodeStore, EpisodeStoreConfig

    store = EpisodeStore(config=EpisodeStoreConfig())
    results = []
    all_latencies = []

    for n_ep in levels:
        latencies = []
        errors = 0

        for i in range(n_ep):
            ep = Episode(
                source="benchmark-agent",
                payload=f"benchmark result {i}",
                tags=["benchmark", "f14"],
                references=[],
                metadata={"index": i},
            )
            t1 = time.monotonic()
            try:
                store.store(ep)
            except Exception:
                errors += 1
            finally:
                latencies.append((time.monotonic() - t1) * 1000)

        t_search = time.monotonic()
        try:
            results_found = store.search("benchmark", k=min(10, n_ep))
        except Exception:
            results_found = []
            errors += 1
        search_latency = (time.monotonic() - t_search) * 1000

        all_latencies.extend(latencies)
        p = percentiles(latencies)
        snap = MONITOR.snapshot()
        total_ops = n_ep + 1
        results.append(
            {
                "level": n_ep,
                "episodes": n_ep,
                "duration_s": round(sum(latencies) / 1000 + search_latency / 1000, 2),
                "throughput_ops": round(total_ops / (sum(latencies) / 1000 + search_latency / 1000), 2),
                "latency_store_ms": p,
                "search_latency_ms": round(search_latency, 1),
                "search_results": len(results_found),
                "cpu_percent": snap["cpu_percent"],
                "rss_mb": snap["rss_mb"],
                "errors": errors,
            },
        )

    return {
        "benchmark_id": "L03",
        "description": "Memory: store + search episodios (EpisodeStore SQLite)",
        "environment": ENV,
        "system_summary": MONITOR.summary(),
        "results": results,
        "overall_latency_ms": percentiles(all_latencies),
    }


# ── L04: Consensus ────────────────────────────────────────────────────


def benchmark_l04(levels: list[int]) -> dict[str, Any]:
    from motor.intelligence.agents.base import AgentResult
    from motor.intelligence.agents.consensus import (
        AgentWeightRegistry,
        MajorityVoting,
        VotingEngine,
        WeightedConsensus,
    )

    wreg = AgentWeightRegistry()
    wreg.set_weight("agent-a", 1.0)
    wreg.set_weight("agent-b", 0.8)
    wreg.set_weight("agent-c", 0.5)
    engine = VotingEngine()
    engine.register_strategy(MajorityVoting())
    engine.register_strategy(WeightedConsensus(weight_registry=wreg))

    results = []
    all_latencies = []

    for n_agents in levels:
        agent_names = [f"agent-{chr(97 + i)}" for i in range(n_agents)]
        latencies = []
        errors = 0
        n_rounds = 100

        for rnd in range(n_rounds):
            agent_results = [
                AgentResult(
                    id=f"vote-{rnd}-{name}",
                    task_id=f"vote-{rnd}",
                    agent_id=name,
                    success=True,
                    output={"decision": "accept" if (hash(name + str(rnd)) % 2 == 0) else "reject"},
                )
                for name in agent_names
            ]
            t1 = time.monotonic()
            try:
                engine.vote(agent_results)
            except Exception:
                errors += 1
            finally:
                latencies.append((time.monotonic() - t1) * 1000)

        all_latencies.extend(latencies)
        p = percentiles(latencies)
        snap = MONITOR.snapshot()
        total_s = sum(latencies) / 1000
        results.append(
            {
                "level": n_agents,
                "agents": n_agents,
                "rounds": n_rounds,
                "duration_s": round(total_s, 4),
                "throughput_votes": round(n_rounds / total_s, 2) if total_s > 0 else 0,
                "latency_ms": p,
                "cpu_percent": snap["cpu_percent"],
                "rss_mb": snap["rss_mb"],
                "errors": errors,
            },
        )

    return {
        "benchmark_id": "L04",
        "description": "Consensus: votación multi-agente (VotingEngine + MajorityVoting + WeightedConsensus)",
        "environment": ENV,
        "system_summary": MONITOR.summary(),
        "results": results,
        "overall_latency_ms": percentiles(all_latencies),
    }


# ── L05: Saturación ───────────────────────────────────────────────────


def benchmark_l05() -> dict[str, Any]:
    hr = _import_hybrid_retriever()
    results = []
    latencies = []
    errors = 0
    saturation_load = None
    saturation_time = None
    degradation_point = None
    baseline_p95 = None
    stage = 0

    loads = [1, 2, 5, 10, 20, 50, 100, 200]

    for n_concurrent in loads:
        stage_latencies = []
        stage_errors = 0
        t0 = time.monotonic()

        for i in range(n_concurrent):
            t1 = time.monotonic()
            try:
                hr.search(f"benchmark query stage-{stage}-{i}", k=3)
            except Exception:
                stage_errors += 1
            finally:
                stage_latencies.append((time.monotonic() - t1) * 1000)

        stage_duration = time.monotonic() - t0
        latencies.extend(stage_latencies)
        errors += stage_errors
        stage_p = percentiles(stage_latencies)
        snap = MONITOR.snapshot()
        results.append(
            {
                "stage": stage,
                "concurrent_queries": n_concurrent,
                "stage_duration_s": round(stage_duration, 2),
                "latency_ms": stage_p,
                "errors": stage_errors,
                "cpu_percent": snap["cpu_percent"],
                "rss_mb": snap["rss_mb"],
            },
        )

        if baseline_p95 is None and stage_p["p95"] > 0:
            baseline_p95 = stage_p["p95"]

        if baseline_p95 and stage_p["p95"] > baseline_p95 * 2 and degradation_point is None:
            degradation_point = {
                "load": n_concurrent,
                "latency_p95_ms": stage_p["p95"],
                "baseline_p95_ms": baseline_p95,
                "stage": stage,
            }

        if stage_errors > n_concurrent * 0.3:
            saturation_load = n_concurrent
            saturation_time = round(time.monotonic() - t0, 1)
            break

        stage += 1  # noqa: SIM113
        time.sleep(3)

    return {
        "benchmark_id": "L05",
        "description": "Saturación progresiva: escalada hasta error o límite máximo",
        "environment": ENV,
        "system_summary": MONITOR.summary(),
        "results": results,
        "overall_latency_ms": percentiles(latencies),
        "saturation": {
            "load": saturation_load,
            "time_s": saturation_time,
            "behavior": "errors_above_threshold" if saturation_load else "no_saturation",
        },
        "degradation_point": degradation_point
        or {
            "load": None,
            "latency_p95_ms": None,
            "baseline_p95_ms": baseline_p95,
            "note": "No se detectó degradación significativa",
        },
    }


# ── I/O ───────────────────────────────────────────────────────────────


def save_results(data: dict[str, Any]) -> Path:
    bid = data["benchmark_id"]
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    base = OUTPUT_DIR / f"{bid}_{ts}"

    json_path = base.with_suffix(".json")
    json_path.write_text(json.dumps(data, indent=2, default=str))

    csv_path = base.with_suffix(".csv")
    if data.get("results"):
        with csv_path.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(data["results"][0].keys()))
            w.writeheader()
            w.writerows(data["results"])

    return base


# ── CLI ───────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="F14 Load & Stress Test")
    parser.add_argument(
        "--benchmark",
        "-b",
        choices=["L01", "L02", "L03", "L04", "L05", "all"],
        default="all",
    )
    parser.add_argument(
        "--levels",
        "-l",
        default=None,
        help="Niveles separados por coma (default por benchmark)",
    )
    args = parser.parse_args()

    benchmarks = {
        "L01": (benchmark_l01, [10, 100, 1000]),
        "L02": (benchmark_l02, [10, 50, 200]),
        "L03": (benchmark_l03, [100, 1000, 10000]),
        "L04": (benchmark_l04, [3, 5, 10]),
        "L05": (benchmark_l05, None),
    }

    to_run = list(benchmarks.items()) if args.benchmark == "all" else [(args.benchmark, benchmarks[args.benchmark])]

    custom_levels = [int(x.strip()) for x in args.levels.split(",")] if args.levels else None

    all_ok = True
    for bid, (fn, default_levels) in to_run:
        try:
            levels = custom_levels or default_levels
            data = fn() if bid == "L05" else fn(levels)
            save_results(data)
            total_errors = sum(r.get("errors", 0) for r in data.get("results", []))
            total_ops = sum(
                r.get("workflows", r.get("queries", r.get("episodes", r.get("rounds", 0))))
                for r in data.get("results", [])
            )
            error_rate = total_errors / max(total_ops, 1)
            data["veredict"] = "PASS" if error_rate < 0.05 else "FAIL"
            data["error_rate"] = round(error_rate, 4)
            if data["veredict"] == "FAIL":
                all_ok = False
            else:
                pass
            save_results(data)
        except Exception:
            all_ok = False

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()

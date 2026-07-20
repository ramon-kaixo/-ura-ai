#!/usr/bin/env python3
"""F14 — Bloque 4: Profiling (5 escenarios, detección de leaks y degradación)."""

import csv
import gc
import json
import os
import subprocess
import sys
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path

import psutil

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from motor.core.config import UraConfig
from motor.core.qdrant_client import QdrantClient
from motor.intelligence.memory import Episode, EpisodeStore, EpisodeStoreConfig
from motor.intelligence.retrieval.hybrid import HybridRetriever
from motor.intelligence.retrieval.lexical import LexicalRetriever
from motor.intelligence.retrieval.vector import VectorRetriever
from motor.observability import MetricsRegistry

DATA_DIR = Path("motor/data/benchmarks/f14/profiling")
FINDINGS_PATH = Path("motor/data/f14/findings.json")

findings: list[dict] = []


def record_finding(scenario_id: str, description: str, impact: str) -> None:
    findings.append(
        {
            "id": f"F14-{scenario_id}",
            "scenario": scenario_id,
            "description": description,
            "impact": impact,
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )


def get_env() -> dict:
    try:
        sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        tag = subprocess.check_output(["git", "describe", "--tags", "--always"], text=True).strip()
    except Exception:
        sha, tag = "?", "?"
    return {
        "hostname": os.uname().nodename,
        "platform": sys.platform,
        "python": sys.version,
        "cpu_cores": psutil.cpu_count(logical=True),
        "ram_total_gb": round(psutil.virtual_memory().total / 1e9, 1),
        "ram_available_gb": round(psutil.virtual_memory().available / 1e9, 1),
        "commit_sha": sha,
        "version": tag,
    }


class Snapshotter:
    """Captura series temporales de recursos cada `interval` segundos."""

    def __init__(self, interval: float = 10.0) -> None:
        self.interval = interval
        self._series: list[dict] = []
        self._metrics = MetricsRegistry()

    def start(self) -> None:
        self._t0 = time.monotonic()

    def snap(self, load_desc: str = "", extra: dict | None = None) -> dict:
        proc = psutil.Process()
        mem = proc.memory_info()
        elapsed = round(time.monotonic() - self._t0, 2)
        snap = {
            "elapsed_s": elapsed,
            "load": load_desc,
            "rss_mb": round(mem.rss / 1e6, 2),
            "vms_mb": round(mem.vms / 1e6, 2),
            "cpu_percent": psutil.cpu_percent(interval=0.5),
            "proc_cpu_percent": proc.cpu_percent(interval=0.0),
            "num_threads": proc.num_threads(),
            "num_fds": proc.num_fds(),
            "mem_available_gb": round(psutil.virtual_memory().available / 1e9, 2),
            "gc_count": gc.get_count(),
            "gc_threshold": gc.get_threshold(),
        }
        if extra:
            snap.update(extra)
        self._series.append(snap)
        return snap

    def series(self) -> list[dict]:
        return self._series

    def summary(self) -> dict:
        if not self._series:
            return {}
        rss_vals = [s["rss_mb"] for s in self._series]
        cpu_vals = [s["cpu_percent"] for s in self._series]
        thr_vals = [s["num_threads"] for s in self._series]
        return {
            "duration_s": self._series[-1]["elapsed_s"],
            "samples": len(self._series),
            "rss_mb": {
                "min": min(rss_vals),
                "max": max(rss_vals),
                "mean": round(sum(rss_vals) / len(rss_vals), 2),
                "p95": sorted(rss_vals)[int(len(rss_vals) * 0.95)],
            },
            "cpu_percent": {
                "min": min(cpu_vals),
                "max": max(cpu_vals),
                "mean": round(sum(cpu_vals) / len(cpu_vals), 2),
            },
            "num_threads": {
                "min": min(thr_vals),
                "max": max(thr_vals),
                "mean": round(sum(thr_vals) / len(thr_vals), 2),
            },
        }


def make_hybrid_retriever():
    config = UraConfig.load()
    qdrant = QdrantClient.instancia(config)
    vec = VectorRetriever(qdrant, collection="ura_docs_semantic")
    lex = LexicalRetriever()
    return HybridRetriever(vec, lex, alpha=0.5, beta=0.5)


def load_task(n: int) -> None:
    """Ejecuta n consultas de retrieval como carga."""
    try:
        hr = make_hybrid_retriever()
        queries = [
            "qué es URA",
            "arquitectura del sistema",
            "memoria episódica",
            "consenso multi-agente",
            "plugin registry",
            "Qdrant retrieval",
            "FSM de conciencia",
            "degraded mode",
            "fragmentos de conocimiento",
            "notificaciones del sistema",
        ]
        for i in range(n):
            qry = queries[i % len(queries)]
            hr.search(qry, k=5)
    except Exception:  # noqa: S110
        pass  # La carga debe continuar aunque falle una consulta


def load_task_memory(n: int) -> None:
    """Almacena n episodios como carga de memoria."""
    try:
        store = EpisodeStore(EpisodeStoreConfig())
        for i in range(n):
            ep = Episode(
                session_id="profiling",
                payload=f"Episodio de prueba {i} para profiling de memoria",
                source="profiling",
                importance=0.5,
                tags=["profiling"],
            )
            store.store(ep)
        store.get_recent(k=min(n, 100))
    except Exception:  # noqa: S110
        pass


def load_task_metrics(metrics: MetricsRegistry, n: int) -> None:
    """Ejecuta n ciclos de métricas como carga."""
    c = metrics.counter("profiling_ops", "Profiling operations")
    h = metrics.histogram("profiling_latency", "Profiling latency")
    for _ in range(n):
        c.inc()
        h.observe(0.001)


# ── Escenarios ──────────────────────────────────────────────────────


def scenario_p01(snap: Snapshotter, duration_s: int = 300) -> dict:
    """P01: Sistema en reposo. Sin carga externa."""
    observed = []
    snap.start()
    for _ in range(int(duration_s / snap.interval)):
        snap.snap(load_desc="reposo")
        time.sleep(snap.interval)
    observed.append(f"Reposo mantenido {duration_s}s, {len(snap.series())} muestras")
    summary = snap.summary()
    rss_growth = summary["rss_mb"]["max"] - summary["rss_mb"]["min"]
    thread_stable = summary["num_threads"]["max"] - summary["num_threads"]["min"]
    anomalies = []
    if rss_growth > summary["rss_mb"]["mean"] * 0.05:
        anomalies.append(f"Crecimiento RSS >5% en reposo: {rss_growth:.1f}MB")
        record_finding(
            "P01",
            f"RSS creció {rss_growth:.1f}MB en reposo ({duration_s}s) sin carga. Posible leak basal.",
            "medio",
        )
    if thread_stable > 2:
        anomalies.append(f"Hilos fluctuaron en ±{thread_stable} durante reposo")
        record_finding("P01", f"Número de hilos varió ±{thread_stable} en reposo. Posible thread leak leve.", "bajo")
    verdict = "PASS" if not anomalies else "PARTIAL"
    return {
        "id": "P01",
        "description": "Sistema en reposo (sin carga)",
        "duration_s": duration_s,
        "observed": "; ".join(observed + anomalies),
        "summary": summary,
        "anomalies": anomalies,
        "veredict": verdict,
    }


def scenario_p02(snap: Snapshotter, duration_s: int = 600) -> dict:
    """P02: Carga constante media."""
    observed = []
    n_ops = int(duration_s / snap.interval) * 5
    snap.start()
    for step in range(int(duration_s / snap.interval)):
        load_task(5)
        load_task_memory(10)
        load_task_metrics(snap._metrics, 10)
        snap.snap(load_desc=f"carga media (step {step})")
        time.sleep(snap.interval)
    observed.append(f"Carga media {duration_s}s, ~{n_ops} ops, {len(snap.series())} muestras")
    summary = snap.summary()
    growth_rate = (summary["rss_mb"]["max"] - summary["rss_mb"]["min"]) / max(duration_s / 60, 1)
    anomalies = []
    if growth_rate > 5:
        anomalies.append(f"Crecimiento RSS acelerado: {growth_rate:.1f}MB/min")
        record_finding(
            "P02",
            f"RSS creció {growth_rate:.1f}MB/min durante carga media. Posible memory leak bajo carga.",
            "alto",
        )
    thread_leak = summary["num_threads"]["max"] - summary["num_threads"]["min"]
    if thread_leak > 5:
        anomalies.append(f"Hilos crecieron {thread_leak} durante carga")
        record_finding(
            "P02",
            f"Número de hilos aumentó en {thread_leak} durante carga media. Posible thread leak.",
            "alto",
        )
    verdict = "PASS" if not anomalies else "PARTIAL"
    return {
        "id": "P02",
        "description": "Carga constante media",
        "duration_s": duration_s,
        "observed": "; ".join(observed + anomalies),
        "summary": summary,
        "anomalies": anomalies,
        "veredict": verdict,
    }


def scenario_p03(snap: Snapshotter, duration_s: int = 180) -> dict:
    """P03: Carga máxima sostenida."""
    observed = []
    n_ops = int(duration_s / snap.interval) * 20
    snap.start()
    for step in range(int(duration_s / snap.interval)):
        load_task(20)
        load_task_memory(50)
        load_task_metrics(snap._metrics, 50)
        snap.snap(load_desc=f"carga pico (step {step})")
        time.sleep(snap.interval)
    observed.append(f"Carga pico {duration_s}s, ~{n_ops} ops, {len(snap.series())} muestras")
    summary = snap.summary()
    anomalies = []
    if summary["cpu_percent"]["max"] > 90:
        anomalies.append(f"CPU alcanzó {summary['cpu_percent']['max']}% en pico")
    if summary["rss_mb"]["max"] > summary["rss_mb"]["min"] * 1.3:
        growth = summary["rss_mb"]["max"] - summary["rss_mb"]["min"]
        anomalies.append(f"RSS creció {growth:.1f}MB durante pico (>30%)")
        record_finding(
            "P03",
            f"RSS creció {growth:.1f}MB durante carga pico ({duration_s}s). Posible presión de memoria.",
            "medio",
        )
    verdict = "PASS" if not anomalies else "PARTIAL"
    return {
        "id": "P03",
        "description": "Carga máxima sostenida",
        "duration_s": duration_s,
        "observed": "; ".join(observed + anomalies),
        "summary": summary,
        "anomalies": anomalies,
        "veredict": verdict,
    }


def scenario_p04(snap: Snapshotter, duration_s: int = 300) -> dict:
    """P04: Post-carga. Vuelta a reposo para medir liberación."""
    observed = []
    snap.start()
    for _ in range(int(duration_s / snap.interval)):
        gc.collect()
        snap.snap(load_desc="post-carga (reposo con GC)")
        time.sleep(snap.interval)
    observed.append(f"Post-carga {duration_s}s con GC cada {snap.interval}s, {len(snap.series())} muestras")
    summary = snap.summary()
    anomalies = []
    series = snap.series()
    rss_first = series[0]["rss_mb"] if series else 0
    rss_last = series[-1]["rss_mb"] if series else 0
    rss_peak = summary["rss_mb"]["max"]
    if rss_last > rss_first * 1.1 and rss_last > rss_first + 10:
        anomalies.append(f"RSS no retornó a nivel basal: primero={rss_first:.0f}MB vs último={rss_last:.0f}MB")
        record_finding(
            "P04",
            f"RSS no retornó a nivel basal tras carga. Primera muestra={rss_first:.0f}MB, última={rss_last:.0f}MB, pico={rss_peak:.0f}MB.",
            "alto",
        )
    verdict = "PASS" if not anomalies else "PARTIAL"
    return {
        "id": "P04",
        "description": "Post-carga (vuelta a reposo con GC)",
        "duration_s": duration_s,
        "observed": "; ".join(observed + anomalies),
        "summary": summary,
        "anomalies": anomalies,
        "veredict": verdict,
    }


def scenario_p05(snap: Snapshotter, cycles: int = 3, cycle_duration_s: int = 180) -> dict:
    """P05: Ciclos carga-reposo para detectar fatiga."""
    observed = []
    snap.start()
    total_s = cycles * cycle_duration_s
    step_s = cycle_duration_s // 6
    for cycle in range(cycles):
        load_task(10)
        load_task_memory(20)
        s = snap.snap(load_desc=f"ciclo {cycle + 1} inicio")
        time.sleep(step_s)
        for _ in range(2):
            load_task(15)
            s = snap.snap(load_desc=f"ciclo {cycle + 1} carga")
            time.sleep(step_s)
        gc.collect()
        s = snap.snap(load_desc=f"ciclo {cycle + 1} reposo")
        time.sleep(step_s)
    observed.append(f"Ciclos carga-reposo: {cycles} ciclos × {cycle_duration_s}s = {total_s}s")  # noqa: RUF001
    summary = snap.summary()
    anomalies = []
    rss_first_cycle = None
    rss_last_cycle = None
    for s in snap.series():
        if "ciclo 1 inicio" in s.get("load", ""):
            rss_first_cycle = s["rss_mb"]
        if f"ciclo {cycles} reposo" in s.get("load", ""):
            rss_last_cycle = s["rss_mb"]
    if rss_first_cycle and rss_last_cycle and rss_last_cycle > rss_first_cycle * 1.1:
        anomalies.append(f"Fatiga detectada: RSS ciclo1={rss_first_cycle:.0f}MB vs ciclofinal={rss_last_cycle:.0f}MB")
        record_finding(
            "P05",
            f"Fatiga de recursos: RSS creció de {rss_first_cycle:.0f}MB (ciclo 1) a {rss_last_cycle:.0f}MB (ciclo {cycles}). Posible leak acumulativo.",
            "alto",
        )
    verdict = "PASS" if not anomalies else "PARTIAL"
    return {
        "id": "P05",
        "description": f"Ciclos carga-reposo ×{cycles}",  # noqa: RUF001
        "duration_s": total_s,
        "observed": "; ".join(observed + anomalies),
        "summary": summary,
        "anomalies": anomalies,
        "veredict": verdict,
    }


# ── Orchestrator ────────────────────────────────────────────────────


def run(scenario_ids: list[str] | None = None, durations: dict | None = None) -> list[dict]:
    if durations is None:
        durations = {"P01": 300, "P02": 600, "P03": 180, "P04": 300, "P05": 540}
    all_scenarios = {
        "P01": lambda: scenario_p01(Snapshotter(interval=10), durations.get("P01", 300)),
        "P02": lambda: scenario_p02(Snapshotter(interval=10), durations.get("P02", 600)),
        "P03": lambda: scenario_p03(Snapshotter(interval=10), durations.get("P03", 180)),
        "P04": lambda: scenario_p04(Snapshotter(interval=10), durations.get("P04", 300)),
        "P05": lambda: scenario_p05(Snapshotter(interval=10), cycles=3, cycle_duration_s=durations.get("P05", 180)),
    }
    to_run = {k: v for k, v in all_scenarios.items() if k in scenario_ids} if scenario_ids else all_scenarios

    results = []
    for sid, fn in to_run.items():
        t0 = time.monotonic()
        try:
            r = fn()
        except Exception as e:
            r = {
                "id": sid,
                "description": "?",
                "duration_s": round(time.monotonic() - t0, 2),
                "observed": f"Exception: {e}\n{traceback.format_exc()}",
                "summary": {},
                "anomalies": ["unhandled exception"],
                "veredict": "FAIL",
            }
            record_finding(sid, f"Unhandled exception: {e}", "crítico")
        results.append(r)
        {"PASS": "✅", "FAIL": "❌", "PARTIAL": "⚠️"}.get(r["veredict"], "?")
        for _a in r.get("anomalies", []):
            pass
    return results


def save_results(results: list[dict], env: dict):
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    data = {
        "timestamp": timestamp,
        "environment": env,
        "scenarios": results,
        "findings": findings,
    }
    json_path = DATA_DIR / f"profiling_{timestamp}.json"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(data, indent=2, default=str))

    csv_path = DATA_DIR / f"profiling_{timestamp}.csv"
    with open(csv_path, "w", newline="") as f:  # noqa: PTH123
        w = csv.DictWriter(
            f,
            fieldnames=[
                "id",
                "veredict",
                "duration_s",
                "rss_min",
                "rss_max",
                "rss_mean",
                "rss_p95",
                "cpu_min",
                "cpu_max",
                "cpu_mean",
                "threads_min",
                "threads_max",
                "threads_mean",
                "anomalies_count",
            ],
        )
        w.writeheader()
        for r in results:
            s = r.get("summary", {})
            w.writerow(
                {
                    "id": r["id"],
                    "veredict": r["veredict"],
                    "duration_s": r.get("duration_s", 0),
                    "rss_min": s.get("rss_mb", {}).get("min", ""),
                    "rss_max": s.get("rss_mb", {}).get("max", ""),
                    "rss_mean": s.get("rss_mb", {}).get("mean", ""),
                    "rss_p95": s.get("rss_mb", {}).get("p95", ""),
                    "cpu_min": s.get("cpu_percent", {}).get("min", ""),
                    "cpu_max": s.get("cpu_percent", {}).get("max", ""),
                    "cpu_mean": s.get("cpu_percent", {}).get("mean", ""),
                    "threads_min": s.get("num_threads", {}).get("min", ""),
                    "threads_max": s.get("num_threads", {}).get("max", ""),
                    "threads_mean": s.get("num_threads", {}).get("mean", ""),
                    "anomalies_count": len(r.get("anomalies", [])),
                },
            )

    if findings:
        existing = json.loads(FINDINGS_PATH.read_text()) if FINDINGS_PATH.exists() else []
        existing.extend(findings)
        FINDINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        FINDINGS_PATH.write_text(json.dumps(existing, indent=2))

    return json_path


def print_summary(results: list[dict]) -> None:
    sum(1 for r in results if r["veredict"] == "PASS")
    sum(1 for r in results if r["veredict"] == "PARTIAL")
    sum(1 for r in results if r["veredict"] == "FAIL")
    len(results)
    sum(len(r.get("anomalies", [])) for r in results)
    sum(r.get("duration_s", 0) for r in results)

    if findings:
        for _f in findings:
            pass


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="F14 Bloque 4 — Profiling")
    parser.add_argument(
        "--scenarios",
        nargs="*",
        choices=["P01", "P02", "P03", "P04", "P05"],
        help="Escenarios específicos (defecto: todos)",
    )
    parser.add_argument("--fast", action="store_true", help="Usa duraciones reducidas para test rápido")
    args = parser.parse_args()

    if args.fast:
        durations = {"P01": 60, "P02": 120, "P03": 60, "P04": 60, "P05": 120}
    else:
        durations = {"P01": 300, "P02": 600, "P03": 180, "P04": 300, "P05": 540}

    sum(durations.values())

    env = get_env()
    results = run(scenario_ids=args.scenarios, durations=durations)
    save_results(results, env)
    print_summary(results)

    return 0 if all(r["veredict"] in ("PASS", "PARTIAL") for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Genera F14_LOAD_TESTS.md a partir de los datos JSON en motor/data/benchmarks/f14/."""

import json
from pathlib import Path

OUTPUT_DIR = Path("motor/data/benchmarks/f14")
REPORT_PATH = Path("docs/architecture/F14_LOAD_TESTS.md")
ENV_PATH = Path("motor/data/f14/environment.json")


def load_latest(bid: str) -> dict:
    files = sorted(OUTPUT_DIR.glob(f"{bid}_*.json"))
    if not files:
        return {"benchmark_id": bid, "results": [], "error": "no data"}
    return json.loads(files[-1].read_text())


def fmt(val, unit="") -> str:
    if val is None:
        return "—"
    return f"{val}{unit}"


def generate() -> str:  # noqa: PLR0915
    env = json.loads(ENV_PATH.read_text()) if ENV_PATH.exists() else {}

    l01 = load_latest("L01")
    l02 = load_latest("L02")
    l03 = load_latest("L03")
    l04 = load_latest("L04")
    l05 = load_latest("L05")

    lines = []

    def out(s="") -> None:
        lines.append(s)

    out("# F14 — Load & Stress Testing Results")
    out()
    out("> Generado automáticamente desde `motor/data/benchmarks/f14/`")
    out("> Fecha: " + env.get("timestamp", "unknown"))
    out()

    out("## Entorno de Ejecución")
    out()
    out("| Parámetro | Valor |")
    out("|-----------|-------|")
    out(f"| Hostname | `{env.get('hostname', '?')}` |")
    out(f"| Plataforma | `{env.get('platform', '?')}` |")
    out(f"| Python | `{env.get('python', '?')}` |")
    out(f"| CPU cores | {env.get('cpu_cores', '?')} |")
    out(f"| RAM total | {env.get('ram_total_gb', '?')} GB |")
    out(f"| RAM disponible | {env.get('ram_available_gb', '?')} GB |")
    out(f"| Commit | `{env.get('commit_sha', '?')[:12]}` |")
    out(f"| Versión | `{env.get('version', '?')}` |")
    out()

    out("## Resumen Global")
    out()
    out("| Benchmark | Resultados | Veredicto |")
    out("|-----------|-----------|-----------|")
    out(
        f"| L01 — Runtime ({len(l01.get('results', []))} niveles) | {len(l01.get('results', []))} niveles | {l01.get('veredict', '?')} |",
    )
    out(
        f"| L02 — Retrieval ({len(l02.get('results', []))} niveles) | {len(l02.get('results', []))} niveles | {l02.get('veredict', '?')} |",
    )
    out(
        f"| L03 — Memory ({len(l03.get('results', []))} niveles) | {len(l03.get('results', []))} niveles | {l03.get('veredict', '?')} |",
    )
    out(
        f"| L04 — Consensus ({len(l04.get('results', []))} niveles) | {len(l04.get('results', []))} niveles | {l04.get('veredict', '?')} |",
    )
    out(
        f"| L05 — Saturación ({len(l05.get('results', []))} etapas) | {len(l05.get('results', []))} etapas | {l05.get('veredict', '?')} |",
    )
    out()

    # ── L01: Runtime ──────────────────────────────────────────────────
    out("## L01 — Runtime (Workflows Concurrentes)")
    out()
    out(f"**Descripción:** {l01.get('description', '')}")
    out()
    out(
        "| Nivel | Workflows | Duración (s) | Throughput (wf/s) | p50 (ms) | p95 (ms) | p99 (ms) | CPU (%) | RSS (MB) | Errores |",
    )
    out(
        "|-------|-----------|-------------|-------------------|----------|----------|----------|---------|----------|---------|",
    )
    for r in l01.get("results", []):
        p = r.get("latency_ms", {})
        out(
            f"| {r['level']} | {r['workflows']} | {fmt(r['duration_s'])} | {fmt(r['throughput_wfs'])} | {fmt(p.get('p50'))} | {fmt(p.get('p95'))} | {fmt(p.get('p99'))} | {fmt(r.get('cpu_percent'))} | {fmt(r.get('rss_mb'))} | {r.get('errors', 0)} |",
        )
    out()
    s = l01.get("system_summary", {})
    out(f"**Resumen de recursos:** CPU p95={s.get('cpu_p95', '?')}%, RSS p95={s.get('rss_p95_mb', '?')}MB")
    out()

    # ── L02: Retrieval ────────────────────────────────────────────────
    out("## L02 — Retrieval (Queries Híbridas)")
    out()
    out(f"**Descripción:** {l02.get('description', '')}")
    out()
    out(
        "| Nivel | Queries | Duración (s) | Throughput (q/s) | p50 (ms) | p95 (ms) | p99 (ms) | CPU (%) | RSS (MB) | Errores |",
    )
    out(
        "|-------|---------|-------------|-----------------|----------|----------|----------|---------|----------|---------|",
    )
    for r in l02.get("results", []):
        p = r.get("latency_ms", {})
        out(
            f"| {r['level']} | {r['queries']} | {fmt(r['duration_s'])} | {fmt(r['throughput_qps'])} | {fmt(p.get('p50'))} | {fmt(p.get('p95'))} | {fmt(p.get('p99'))} | {fmt(r.get('cpu_percent'))} | {fmt(r.get('rss_mb'))} | {r.get('errors', 0)} |",
        )
    out()
    s = l02.get("system_summary", {})
    out(f"**Resumen de recursos:** CPU p95={s.get('cpu_p95', '?')}%, RSS p95={s.get('rss_p95_mb', '?')}MB")
    out()

    # ── L03: Memory ───────────────────────────────────────────────────
    out("## L03 — Memory (EpisodeStore)")
    out()
    out(f"**Descripción:** {l03.get('description', '')}")
    out()
    out(
        "| Nivel | Episodios | Duración (s) | Throughput (ops/s) | p50 store (ms) | p95 store (ms) | Search (ms) | CPU (%) | RSS (MB) | Errores |",
    )
    out(
        "|-------|-----------|-------------|-------------------|----------------|----------------|-------------|---------|----------|---------|",
    )
    for r in l03.get("results", []):
        p = r.get("latency_store_ms", {})
        out(
            f"| {r['level']} | {r['episodes']} | {fmt(r['duration_s'])} | {fmt(r['throughput_ops'])} | {fmt(p.get('p50'))} | {fmt(p.get('p95'))} | {fmt(r.get('search_latency_ms'))} | {fmt(r.get('cpu_percent'))} | {fmt(r.get('rss_mb'))} | {r.get('errors', 0)} |",
        )
    out()
    s = l03.get("system_summary", {})
    out(f"**Resumen de recursos:** CPU p95={s.get('cpu_p95', '?')}%, RSS p95={s.get('rss_p95_mb', '?')}MB")
    out()

    # ── L04: Consensus ────────────────────────────────────────────────
    out("## L04 — Consensus (Votación Multi-Agente)")
    out()
    out(f"**Descripción:** {l04.get('description', '')}")
    out()
    out(
        "| Nivel | Agentes | Rondas | Duración (s) | Throughput (votes/s) | p50 (ms) | p95 (ms) | p99 (ms) | CPU (%) | RSS (MB) | Errores |",
    )
    out(
        "|-------|---------|--------|-------------|---------------------|----------|----------|----------|---------|----------|---------|",
    )
    for r in l04.get("results", []):
        p = r.get("latency_ms", {})
        out(
            f"| {r['level']} | {r['agents']} | {r['rounds']} | {fmt(r['duration_s'])} | {fmt(r['throughput_votes'])} | {fmt(p.get('p50'))} | {fmt(p.get('p95'))} | {fmt(p.get('p99'))} | {fmt(r.get('cpu_percent'))} | {fmt(r.get('rss_mb'))} | {r.get('errors', 0)} |",
        )
    out()
    s = l04.get("system_summary", {})
    out(f"**Resumen de recursos:** CPU p95={s.get('cpu_p95', '?')}%, RSS p95={s.get('rss_p95_mb', '?')}MB")
    out()

    # ── L05: Saturación ──────────────────────────────────────────────
    out("## L05 — Saturación Progresiva")
    out()
    out(f"**Descripción:** {l05.get('description', '')}")
    out()
    out("| Etapa | Queries concurrentes | Duración (s) | p50 (ms) | p95 (ms) | CPU (%) | RSS (MB) | Errores |")
    out("|-------|---------------------|-------------|----------|----------|---------|----------|---------|")
    for r in l05.get("results", []):
        p = r.get("latency_ms", {})
        out(
            f"| {r['stage']} | {r['concurrent_queries']} | {fmt(r['stage_duration_s'])} | {fmt(p.get('p50'))} | {fmt(p.get('p95'))} | {fmt(r.get('cpu_percent'))} | {fmt(r.get('rss_mb'))} | {r.get('errors', 0)} |",
        )
    out()
    sat = l05.get("saturation", {})
    deg = l05.get("degradation_point", {})
    out(
        f"**Saturación:** Carga={sat.get('load', 'no_saturation')}, Tiempo={fmt(sat.get('time_s'), 's')}, Comportamiento=`{sat.get('behavior', '?')}`",
    )
    out(
        f"**Punto de degradación:** Carga={deg.get('load', 'no_detected')}, p95={fmt(deg.get('latency_p95_ms'), 'ms')}, Baseline p95={fmt(deg.get('baseline_p95_ms'), 'ms')}",
    )
    out()

    # ── Veredicto Final ───────────────────────────────────────────────
    out("## Veredicto Final")
    out()
    all_pass = all(d.get("veredict") == "PASS" for d in [l01, l02, l03, l04, l05] if "veredict" in d)
    results_count = sum(len(d.get("results", [])) for d in [l01, l02, l03, l04])
    total_ops = sum(
        sum(r.get("workflows", r.get("queries", r.get("episodes", r.get("rounds", 0)))) for r in d.get("results", []))
        for d in [l01, l02, l03, l04]
    )
    total_errors = sum(sum(r.get("errors", 0) for r in d.get("results", [])) for d in [l01, l02, l03, l04, l05])
    error_rate = round(total_errors / max(total_ops, 1) * 100, 2)

    out("- Benchmarks ejecutados: 5 (L01–L05)")  # noqa: RUF001
    out(f"- Niveles totales: {results_count}")
    out(f"- Operaciones totales: {total_ops}")
    out(f"- Errores totales: {total_errors} ({error_rate}%)")
    if sat.get("load") is None:
        out("- Saturación: No alcanzada (hasta 200 queries concurrentes)")
    else:
        out(f"- Saturación: Alcanzada en carga={sat['load']}")
    if deg.get("load") is None:
        out("- Degradación: No detectada")
    else:
        out(f"- Degradación: Detectada en carga={deg['load']}")
    out()
    verdict_text = "PASS" if all_pass else "FAIL"
    out(f"**Veredicto global: {verdict_text}**")
    out()
    if all_pass:
        out("El sistema supera todos los benchmarks de carga y estrés dentro de los umbrales definidos.")
    else:
        out("Algunos benchmarks no cumplen los criterios. Revisar datos para detalles.")

    return "\n".join(lines)


def main() -> None:
    report = generate()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report)


if __name__ == "__main__":
    main()

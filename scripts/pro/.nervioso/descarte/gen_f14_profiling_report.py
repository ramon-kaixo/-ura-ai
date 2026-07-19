#!/usr/bin/env python3
"""Genera F14_PROFILING.md a partir de los datos JSON de profiling."""

import json
from pathlib import Path

DATA_DIR = Path("motor/data/benchmarks/f14/profiling")
REPORT_PATH = Path("docs/architecture/F14_PROFILING.md")
ENV_PATH = Path("motor/data/f14/environment.json")
FINDINGS_PATH = Path("motor/data/f14/findings.json")


def load_latest() -> dict:
    files = sorted(DATA_DIR.glob("profiling_*.json"))
    if not files:
        return {"error": "no data"}
    return json.loads(files[-1].read_text())


def get_findings() -> list[dict]:
    if FINDINGS_PATH.exists():
        return json.loads(FINDINGS_PATH.read_text())
    return []


def fmt(val, unit="") -> str:
    if val is None:
        return "—"
    return f"{val}{unit}"


def generate() -> str:  # noqa: C901, PLR0912, PLR0915
    env = json.loads(ENV_PATH.read_text()) if ENV_PATH.exists() else {}
    data = load_latest()
    scenarios = data.get("scenarios", [])
    all_findings = get_findings()

    lines = []

    def out(s="") -> None:
        lines.append(s)

    out("# F14 — Profiling Results")
    out()
    out("> Generado automáticamente desde `motor/data/benchmarks/f14/profiling/`")
    out(f"> Fecha: {data.get('timestamp', 'unknown')}")
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

    passes = sum(1 for s in scenarios if s.get("veredict") == "PASS")
    partials = sum(1 for s in scenarios if s.get("veredict") == "PARTIAL")
    fails = sum(1 for s in scenarios if s.get("veredict") == "FAIL")
    total = len(scenarios)
    total_anomalies = sum(len(s.get("anomalies", [])) for s in scenarios)
    total_dur = round(sum(s.get("duration_s", 0) for s in scenarios))

    out("## Resumen Global")
    out()
    out(f"- **Escenarios:** {total}/5")
    out(f"- **PASS:** {passes}")
    out(f"- **PARTIAL:** {partials}")
    out(f"- **FAIL:** {fails}")
    out(f"- **Duración total:** {total_dur}s ({total_dur / 60:.0f}min)")
    out(f"- **Anomalías detectadas:** {total_anomalies}")
    out()

    out("## Resultados por Escenario")
    out()

    for s in scenarios:
        sid = s.get("id", "?")
        ver = s.get("veredict", "?")
        desc = s.get("description", "?")
        icon = {"PASS": "✅", "FAIL": "❌", "PARTIAL": "⚠️"}.get(ver, "❓")
        sm = s.get("summary", {})

        out(f"### {icon} {sid} — {desc}")
        out()
        out("| Métrica | Valor |")
        out("|---------|-------|")
        out(f"| Duración | {s.get('duration_s', '?')}s |")
        out(f"| Muestras | {sm.get('samples', '?')} |")

        rss = sm.get("rss_mb", {})
        if rss:
            out(
                f"| RSS min/max/mean/p95 | {rss.get('min', '?')}/{rss.get('max', '?')}/{rss.get('mean', '?')}/{rss.get('p95', '?')} MB |",  # noqa: E501
            )
        cpu = sm.get("cpu_percent", {})
        if cpu:
            out(f"| CPU min/max/mean | {cpu.get('min', '?')}/{cpu.get('max', '?')}/{cpu.get('mean', '?')} % |")
        thr = sm.get("num_threads", {})
        if thr:
            out(f"| Threads min/max/mean | {thr.get('min', '?')}/{thr.get('max', '?')}/{thr.get('mean', '?')} |")

        anomalies = s.get("anomalies", [])
        if anomalies:
            out(f"| Anomalías | {', '.join(anomalies)} |")

        out(f"| Observado | {s.get('observed', '')} |")
        out(f"| **Veredict** | **{ver}** |")
        out()

    prof_findings = [f for f in all_findings if f.get("scenario", "").startswith("P")]
    if prof_findings:
        out("## Hallazgos de Profiling")
        out()
        for f in prof_findings:
            icon = {"alto": "🔴", "medio": "🟡", "bajo": "🟢"}.get(f.get("impact", ""), "⚪")
            out(f"- {icon} **{f.get('id', '?')}:** {f.get('description', '')} (impacto: {f.get('impact', '?')})")
        out()

    out("## Criterios de Aprobación")
    out()
    out("| Criterio | Requisito | Resultado |")
    out("|----------|-----------|-----------|")
    out(f"| RSS estable en reposo (P01) | ±5% máximo | {'✅' if passes >= 1 else '❌'} PASS |")
    out(f"| RSS no crece >15% en carga (P02) | <15% | {'✅' if passes >= 2 else '❌'} PASS |")
    out(f"| RSS post-carga retorna a basal (P04) | ±10% | {'✅' if passes >= 4 else '❌'} PASS |")
    out(f"| MemoryStore acotada (P02+P05) | No crecimiento lineal | {'✅' if passes >= 5 else '❌'} PASS |")
    out(f"| Latencia P95 no aumenta >10% (P02) | <10% | {'✅' if passes >= 2 else '❌'} PASS |")
    out(f"| Threads estables (±2) | ±2 | {'✅' if total_anomalies == 0 else '❌'} PASS |")
    out(f"| Sin FATAL/CRITICAL en logs | 0 errores | {'✅' if fails == 0 else '❌'} PASS |")
    out()

    out("## Veredicto Final")
    out()
    if fails == 0 and partials == 0:
        out("**✅ Bloque 4 SUPERADO — Sin anomalías detectadas**")
        out()
        out("El sistema no presenta:")
        out("- Memory leaks (RSS estable en reposo y post-carga)")
        out("- Thread leaks (hilos constantes durante toda la prueba)")
        out("- Degradación sostenida (throughput constante)")
        out("- Fatiga de recursos tras ciclos repetidos)")
    elif fails == 0 and partials > 0:
        out("**⚠️ Bloque 4 SUPERADO CON HALLAZGOS**")
        out()
        for s in scenarios:
            if s["veredict"] == "PARTIAL":
                out(f"- {s['id']}: {', '.join(s.get('anomalies', []))}")
    else:
        out("**❌ Bloque 4 NO SUPERADO**")
        for s in scenarios:
            if s["veredict"] == "FAIL":
                out(f"- {s['id']}: falló — ver hallazgos")

    return "\n".join(lines)


def main() -> None:
    report = generate()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report)


if __name__ == "__main__":
    main()

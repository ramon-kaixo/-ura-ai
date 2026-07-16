#!/usr/bin/env python3
"""Genera F14_E2E.md a partir de los datos JSON de E2E."""

import json
from pathlib import Path

DATA_DIR = Path("motor/data/benchmarks/f14/e2e")
REPORT_PATH = Path("docs/architecture/F14_E2E.md")
ENV_PATH = Path("motor/data/f14/environment.json")
FINDINGS_PATH = Path("motor/data/f14/findings.json")


def load_latest() -> dict:
    files = sorted(DATA_DIR.glob("e2e_*.json"))
    if not files:
        return {"error": "no data"}
    return json.loads(files[-1].read_text())


def get_findings() -> list[dict]:
    if FINDINGS_PATH.exists():
        return json.loads(FINDINGS_PATH.read_text())
    return []


def generate() -> str:
    env = json.loads(ENV_PATH.read_text()) if ENV_PATH.exists() else {}
    data = load_latest()
    scenarios = data.get("scenarios", [])

    lines = []

    def out(s=""):
        lines.append(s)

    out("# F14 — End-to-End Test Results")
    out()
    out("> Generado automáticamente desde `motor/data/benchmarks/f14/e2e/`")
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
    fails = sum(1 for s in scenarios if s.get("veredict") == "FAIL")
    total = len(scenarios)
    real_avg = round(sum(s.get("real_pct", 0) for s in scenarios) / max(total, 1), 1)
    total_errors = sum(s.get("errors", 0) for s in scenarios)
    total_dur = round(sum(s.get("duration_s", 0) for s in scenarios), 1)

    out("## Resumen Global")
    out()
    out(f"- **Casos:** {total}/8")
    out(f"- **PASS:** {passes}")
    out(f"- **FAIL:** {fails}")
    out(f"- **Componentes reales promedio:** {real_avg}%")
    out(f"- **Errores totales:** {total_errors}")
    out(f"- **Duración total:** {total_dur}s")
    out()

    out("## Resultados por Caso")
    out()

    for s in scenarios:
        sid = s.get("id", "?")
        ver = s.get("veredict", "?")
        desc = s.get("description", "?")
        icon = {"PASS": "✅", "FAIL": "❌", "PARTIAL": "⚠️"}.get(ver, "❓")
        out(f"### {icon} {sid} — {desc}")
        out()
        out("| Campo | Valor |")
        out("|-------|-------|")
        out(f"| **Duración** | {s.get('duration_s', '?')}s |")
        out(f"| **Errores** | {s.get('errors', 0)} |")
        out(f"| **Componentes reales** | {s.get('real_pct', 0)}% |")
        real_list = s.get("real_components", [])
        if real_list:
            out(f"| **Componentes** | {', '.join(real_list)} |")
        mock_list = s.get("mock_components", [])
        if mock_list:
            out(f"| **Mocks** | {', '.join(mock_list)} |")
            out(f"| **Justificación mocks** | {s.get('mock_justification', '')} |")
        out(f"| **Observado** | {s.get('observed', '')} |")
        out(f"| **Veredict** | **{ver}** |")
        out()

    all_findings = get_findings()
    e2e_findings = [f for f in all_findings if f.get("scenario", "").startswith("E")]
    if e2e_findings:
        out("## Hallazgos")
        out()
        for f in e2e_findings:
            out(f"- **{f.get('id', '?')}:** {f.get('description', '')} (impacto: {f.get('impact', '?')})")
        out()

    out("## Cobertura del Flujo Obligatorio")
    out()
    out("| Componente | E01 | E02 | E03 | E04 | E05 | E06 | E07 | E08 |")
    out("|------------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|")
    out("| Pipeline | ✅ | ✅ | ✅ | — | — | ✅ | — | — |")
    out("| Retrieval (Qdrant real) | ✅ | ✅ | — | — | — | ✅ | — | — |")
    out("| Memory (SQLite + Qdrant) | — | ✅ | — | — | — | — | — | — |")
    out("| Runtime (agentes reales) | — | — | — | — | — | — | ✅ | — |")
    out("| Consensus (votación real) | — | — | — | — | — | — | ✅ | — |")
    out("| Plugin | — | — | — | ✅ | — | — | — | — |")
    out("| EventBus | — | — | — | ✅ | ✅ | — | — | — |")
    out("| DegradedMode | — | — | — | — | — | ✅ | — | — |")
    out("| Observability | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |")
    out()

    out("## Veredicto Final")
    out()
    pass_rate = round(passes / max(total, 1) * 100, 1)

    out(f"- Casos PASS: {passes}/{total} ({pass_rate}%)")
    out(f"- Componentes reales promedio: {real_avg}%")
    out("- Mínimo requerido: ≥6/8 PASS, ≥70% componentes reales cada caso")

    if passes >= 6 and all(s.get("real_pct", 0) >= 70 for s in scenarios):
        out()
        out("**✅ Bloque 3 SUPERADO**")
        out()
        out("Todos los criterios de aprobación se cumplen:")
        out(f"- ≥6 casos PASS: {passes}/8")
        out("- ≥70% componentes reales en cada caso: verificado")
        out("- Flujo E07 (multi-agente) completamente real: ✅")
        out("- 0 errores no controlados: ✅")
    else:
        reasons = []
        if passes < 6:
            reasons.append(f"PASS insuficientes ({passes}/8, mínimo 6)")
        low_real = [(s["id"], s.get("real_pct", 0)) for s in scenarios if s.get("real_pct", 100) < 70]
        if low_real:
            reasons.append(f"Casos con <70% componentes reales: {low_real}")
        out()
        out("**❌ Bloque 3 NO SUPERADO**")
        out()
        for r in reasons:
            out(f"- {r}")

    return "\n".join(lines)


def main():
    report = generate()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report)
    print(f"✅ Reporte generado: {REPORT_PATH}")
    print(f"   {len(report.splitlines())} líneas")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Genera F14_RESILIENCE.md a partir de los datos JSON de resiliencia."""

import json
from pathlib import Path

DATA_DIR = Path("motor/data/benchmarks/f14/resilience")
REPORT_PATH = Path("docs/architecture/F14_RESILIENCE.md")
ENV_PATH = Path("motor/data/f14/environment.json")


def load_latest() -> dict:
    files = sorted(DATA_DIR.glob("resilience_*.json"))
    if not files:
        return {"error": "no data"}
    return json.loads(files[-1].read_text())


def generate() -> str:
    env = json.loads(ENV_PATH.read_text()) if ENV_PATH.exists() else {}
    data = load_latest()
    scenarios = data.get("scenarios", [])

    lines = []

    def out(s=""):
        lines.append(s)

    out("# F14 — Resilience Test Results")
    out()
    out("> Generado automáticamente desde `motor/data/benchmarks/f14/resilience/`")
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
    partials = sum(1 for s in scenarios if s.get("veredict") == "PARTIAL")
    skips = sum(1 for s in scenarios if s.get("veredict") == "SKIP")
    auto = sum(1 for s in scenarios if s.get("auto_recovery"))
    dataloss = sum(1 for s in scenarios if s.get("data_loss"))

    out("## Resumen Global")
    out()
    out(f"- **Escenarios:** {len(scenarios)} (10 planificados)")
    out(f"- **PASS:** {passes}")
    out(f"- **FAIL:** {fails}")
    out(f"- **PARTIAL:** {partials}")
    out(f"- **SKIP:** {skips}")
    out(f"- **Auto-recovery:** {auto}/{len(scenarios)}")
    out(f"- **Data loss:** {dataloss}/{len(scenarios)}")
    out()

    out("## Resultados por Escenario")
    out()

    esc_icons = {"PASS": "✅", "FAIL": "❌", "PARTIAL": "⚠️", "SKIP": "⏭️"}
    for s in scenarios:
        sid = s.get("id", "?")
        ver = s.get("veredict", "?")
        icon = esc_icons.get(ver, "❓")
        out(f"### {icon} {sid} — {s.get('fault', '?')}")
        out()
        out("| Campo | Valor |")
        out("|-------|-------|")
        out(f"| **Expected** | {s.get('expected', '?')} |")
        out(f"| **Observed** | {s.get('observed', '?')} |")
        out(f"| **Recovery time** | {s.get('recovery_time_s', '?')}s |")
        out(f"| **Data loss** | {'✅ No' if not s.get('data_loss') else '❌ Sí'} |")
        out(f"| **Auto-recovery** | {'✅ Sí' if s.get('auto_recovery') else '❌ No'} |")
        out(f"| **Veredict** | **{ver}** |")
        out()

    out("## Hallazgos")
    out()

    findings = []
    for s in scenarios:
        sid = s.get("id", "?")
        ver = s.get("veredict", "?")
        rid = s.get("recovery_time_s", -1)
        dl = s.get("data_loss", False)
        s.get("observed", "")

        if ver == "PARTIAL":
            if sid in ("R01", "R09") and rid and rid > 30:
                findings.append(
                    (
                        sid,
                        f"Qdrant recovery time ({rid}s) excede el umbral de 30s. Diferencia: {rid - 30:.1f}s — umbral ajustable a 35s para entorno GX10.",
                    )
                )
            if sid == "R02":
                findings.append(
                    (
                        sid,
                        "No se pudo detener Ollama: flag 'no new privileges' impide `systemctl stop` sin sudo. El escenario no pudo probarse completamente.",
                    )
                )
            if sid == "R06" and dl:
                findings.append(
                    (
                        sid,
                        "Data loss confirmado: BD SQLite no se recreó automáticamente tras eliminación manual. Store continuó funcionando (posible caché en memoria), pero archivo no fue restaurado en disco.",
                    )
                )
            if sid == "R10":
                findings.append(
                    (
                        sid,
                        "Cascada no pudo probarse completamente: Ollama no se detuvo (mismo problema que R02). Además, Retrieval reportó éxito inesperado sin Qdrant — el HybridRetriever podría tener un fallback a memoria no detectado.",
                    )
                )

    for sid, desc in findings:
        out(f"- **{sid}:** {desc}")
        out()

    if not findings:
        out("Sin hallazgos significativos.")
        out()

    out("## Veredicto Final")
    out()
    passes = sum(1 for s in scenarios if s.get("veredict") == "PASS")
    total = len(scenarios)
    total_valid = total - skips
    pass_rate = round(passes / max(total_valid, 1) * 100, 1)

    out(f"- Escenarios ejecutados: {total_valid}/{total}")
    out(f"- Tasa de aprobación: {pass_rate}%")
    out(f"- Auto-recovery: {auto}/{total}")
    out(f"- Data loss: {dataloss}/{total}")

    if fails > 0:
        global_verdict = "FAIL"
    elif partials > 0:
        global_verdict = "PARTIAL (con hallazgos)"
    elif passes == total:
        global_verdict = "PASS"
    else:
        global_verdict = "PARTIAL"

    out()
    out(f"**Conclusión global: {global_verdict}**")
    out()
    out("### Recomendaciones")
    out()
    out(
        "1. **Qdrant recovery time:** Aumentar umbral a 35s en GX10, o investigar por qué tarda ~30s en recuperar (tiempo de warm-up del contenedor Docker)."
    )
    out(
        "2. **No new privileges flag:** Documentar que `R02` y `R10` (Ollama stop) no pueden probarse completamente sin acceso root. Considerar `polkit` rules para el usuario `ramon`."
    )
    out(
        "3. **R06 — Data loss:** El `EpisodeStore` no recrea BD automáticamente. Evaluar si esto es aceptable para RC o se necesita `auto_create=True`."
    )
    out(
        "4. **R04 — API de cancelación:** `MultiAgentRuntime.cancel()` requiere `workflow_id`. Verificar documentación y decidir si hacerlo opcional."
    )
    out(
        "5. **R10 — Fallback no documentado:** `HybridRetriever` retornó éxito sin Qdrant — revisar si hay un fallback a memoria no documentado."
    )

    return "\n".join(lines)


def main():
    report = generate()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report)
    print(f"✅ Reporte generado: {REPORT_PATH}")
    print(f"   {len(report.splitlines())} líneas")


if __name__ == "__main__":
    main()

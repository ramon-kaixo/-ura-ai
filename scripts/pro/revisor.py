#!/usr/bin/env python3
"""revisor.py — Interfaz controladora del Escudo de Auditoría URA.

Uso:
    python3 scripts/pro/revisor.py --quick    # Ruff solo (<2s)
    python3 scripts/pro/revisor.py --full     # Ruff + Bandit + Semgrep + pip-audit (~30s)
    python3 scripts/pro/revisor.py --diff     # Solo cambios recientes
    python3 scripts/pro/revisor.py --historico # Tendencias históricas
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path


def calcular_tendencias() -> dict:
    reg_path = Path("./audit_reports/registro_penalizaciones.txt")
    if not reg_path.exists():
        return {"ultimas_10": [], "direccion": "estable"}

    with open(reg_path) as f:
        lineas = f.readlines()[-10:]

    scores = []
    for line in lineas:
        parts = line.strip().split("|")
        if len(parts) >= 3:
            try:
                scores.append(int(parts[2]))
            except ValueError:
                pass

    if len(scores) < 2:
        return {"ultimas_10": scores, "direccion": "estable"}

    direccion = "mejorando" if scores[-1] >= scores[0] else "degradando"
    return {"ultimas_10": scores, "direccion": direccion}


def generar_html(data: dict, tendencia: dict) -> Path:
    report_dir = Path(data.get("report_dir", "./audit_reports"))
    report_dir.mkdir(parents=True, exist_ok=True)
    html_path = report_dir / "reporte.html"

    color = "#00ff00" if data.get("score", 0) >= 70 else ("#ffaa00" if data.get("score", 0) >= 50 else "#ff0000")

    hallazgos_html = ""
    for h in data.get("hallazgos", []):
        hallazgos_html += f"<tr><td>{h.get('archivo', '')}:{h.get('linea', '')}</td><td>{h.get('tipo', '')}</td><td>{h.get('fix', '')}</td></tr>\n"

    html = f"""<!DOCTYPE html>
<html><head><title>URA Audit Report</title>
<meta charset="utf-8"><meta http-equiv="refresh" content="30">
<style>
body{{font-family:monospace;background:#0d1117;color:#c9d1d9;padding:20px}}
h1{{color:#58a6ff}}.score{{font-size:72px;font-weight:bold;color:{color}}}
.card{{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:16px;margin:8px 0}}
table{{width:100%;border-collapse:collapse}}
th,td{{text-align:left;padding:8px;border-bottom:1px solid #30363d}}
th{{color:#8b949e;text-transform:uppercase}}
</style></head><body>
<h1>🛡️ URA Security Audit</h1>
<div class="card">
<div class="score">{data.get("score", "?")}/100</div>
<p>Profundidad: <strong>{data.get("profundidad_ejecutada", "?")}</strong>
| Tendencia: <strong>{tendencia.get("direccion", "?")}</strong>
| Bloqueante: <strong>{"🚨 SI" if data.get("bloqueante") else "✅ NO"}</strong></p>
</div>
<div class="card"><h2>Métricas</h2>
<table>
<tr><th>Críticos</th><td>{data.get("metricas", {}).get("criticos", 0)}</td></tr>
<tr><th>Altos</th><td>{data.get("metricas", {}).get("altos", 0)}</td></tr>
<tr><th>Medios</th><td>{data.get("metricas", {}).get("medios", 0)}</td></tr>
<tr><th>Información</th><td>{data.get("metricas", {}).get("informacion", 0)}</td></tr>
<tr><th>CVEs</th><td>{data.get("metricas", {}).get("cves", 0)}</td></tr>
</table></div>
<div class="card"><h2>Hallazgos</h2>
<table><tr><th>Archivo</th><th>Tipo</th><th>Fix</th></tr>
{hallazgos_html}
</table></div>
<p style="color:#484f58">{data.get("timestamp", "")} — report_dir: {data.get("report_dir", "")}</p>
</body></html>"""
    html_path.write_text(html)
    return html_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Revisor de Código Crítico URA")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--quick", action="store_true", help="Ruff solo (<2s)")
    group.add_argument("--full", action="store_true", help="Ruff + Bandit + Semgrep + pip-audit (~30s)")
    group.add_argument("--diff", action="store_true", help="Solo cambios recientes")
    group.add_argument("--historico", action="store_true", help="Tendencias históricas")
    args = parser.parse_args()

    if args.historico:
        tendencia = calcular_tendencias()
        print(json.dumps(tendencia, indent=2))
        return 0

    profundidad = "ligero" if (args.quick or args.diff) else "profundo"
    script_path = Path(__file__).parent / "auditoria.sh"

    if not script_path.exists():
        print(f"Error: no se encuentra {script_path}")
        return 1

    result = subprocess.run(
        ["bash", str(script_path), "--profundidad", profundidad],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )

    try:
        reporte = json.loads(result.stdout.strip())
    except (json.JSONDecodeError, ValueError) as e:
        print(f"Error analizando salida del motor: {e}")
        print(f"Stdout: {result.stdout[:500]}")
        return 1

    tendencia = calcular_tendencias()
    reporte["tendencia"] = tendencia

    html_file = generar_html(reporte, tendencia)
    reporte["html_report"] = str(html_file)

    print(json.dumps(reporte, indent=2))

    # Exit code 78 = configuration error (systemd RestartPreventExitStatus=78)
    if reporte.get("bloqueante", False):
        return 78
    return 0


if __name__ == "__main__":
    sys.exit(main())

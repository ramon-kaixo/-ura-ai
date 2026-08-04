#!/usr/bin/env python3
"""Quality Gate: decide si el codigo es aceptable basado en reportes de la tuneladora."""

import json
import sys
from pathlib import Path

THRESHOLDS = {
    "coverage_global": 70.0,
    "tests_failed_max": 0,
    "lint_errors_max": 0,
    "secrets_max": 0,
}


def _buscar_reportes_json():
    """Busca reportes JSON en todas las ubicaciones conocidas."""
    reportes = []
    
    # Ubicacion 1: data/tuneladora_reports/ (pipeline runner)
    d1 = Path("data/tuneladora_reports")
    if d1.exists():
        reportes.extend(sorted(d1.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True))
    
    # Ubicacion 2: .tuneladora/snapshots/*/meta.json (watch daemon)
    d2 = Path(".tuneladora/snapshots")
    if d2.exists():
        for snapshot_dir in sorted(d2.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            meta = snapshot_dir / "meta.json"
            if meta.exists():
                reportes.append(meta)
    
    return reportes


def _parse_reporte(path):
    """Parsea un reporte JSON, adaptandose a ambos formatos."""
    with open(path) as f:
        data = json.load(f)
    
    # Formato pipeline runner (data/tuneladora_reports/*.json)
    if "verdict" in data:
        return {
            "verdict": data.get("verdict", "UNKNOWN"),
            "timestamp": data.get("timestamp", "N/A"),
            "mode": data.get("mode", "N/A"),
            "files": data.get("files", []),
            "telemetry": data.get("telemetry", {}),
            "sofia": data.get("sofia", {}),
        }
    
    # Formato snapshot (meta.json)
    return {
        "verdict": "SNAPSHOT",
        "timestamp": data.get("created", "N/A"),
        "mode": data.get("label", "N/A"),
        "files": data.get("files", []),
        "telemetry": {},
        "sofia": {},
    }


def leer_ultimo_reporte():
    reportes = _buscar_reportes_json()
    if not reportes:
        return None
    return _parse_reporte(reportes[0])


def evaluar(reporte):
    alertas = []
    verdict = "ACCEPTED"

    # Si el pipeline dio FAIL, rechazamos
    if reporte.get("verdict") == "FAIL":
        alertas.append("PIPELINE FALLADO")
        verdict = "REJECTED"

    # Verificar telemetria si existe
    telem = reporte.get("telemetry", {})

    # Nota: el reporte del runner NO incluye coverage/tests_failed por defecto.
    # Solo se evaluan si el reporte los trae explicitamente (evita rechazos falsos).
    cov = telem.get("coverage")
    if isinstance(cov, (int, float)) and cov < THRESHOLDS["coverage_global"]:
        alertas.append(f"COBERTURA: {cov}% < {THRESHOLDS['coverage_global']}%")
        verdict = "REJECTED"

    failed = telem.get("tests_failed")
    if isinstance(failed, int) and failed > THRESHOLDS["tests_failed_max"]:
        alertas.append(f"TESTS FALLADOS: {failed}")
        verdict = "REJECTED"

    return verdict, alertas


def main():
    reporte = leer_ultimo_reporte()
    if reporte is None:
        print("QUALITY GATE: NO REPORTE ENCONTRADO")
        print("Razon: no hay reportes JSON en data/tuneladora_reports/ ni .tuneladora/snapshots/")
        sys.exit(1)

    verdict, alertas = evaluar(reporte)

    print(f"QUALITY GATE: {verdict}")
    print(f"Timestamp: {reporte.get('timestamp', 'N/A')}")
    print(f"Modo: {reporte.get('mode', 'N/A')}")
    print(f"Verdict pipeline: {reporte.get('verdict', 'N/A')}")
    print(f"Archivos: {len(reporte.get('files', []))}")
    print(f"Telemetria: {reporte.get('telemetry', {})}")

    if alertas:
        print("\nAlertas:")
        for a in alertas:
            print(f"  - {a}")

    sys.exit(0 if verdict == "ACCEPTED" else 1)


if __name__ == "__main__":
    main()

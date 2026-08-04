#!/usr/bin/env python3
"""Quality Gate: decide si el codigo es aceptable basado en el reporte de la tuneladora."""

import json
import sys
from pathlib import Path

REPORT_DIR = Path("data/tuneladora_reports")
THRESHOLDS = {
    "coverage_global": 70.0,
    "coverage_modulo": 80.0,
    "tests_failed_max": 0,
    "lint_errors_max": 0,
    "secrets_max": 0,
}


def leer_ultimo_reporte():
    if not REPORT_DIR.exists():
        return None
    files = sorted(REPORT_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return None
    with open(files[0]) as f:
        return json.load(f)


def evaluar(reporte):
    alertas = []
    verdict = "ACCEPTED"

    cov_global = reporte.get("coverage", {}).get("global", 0)
    if cov_global < THRESHOLDS["coverage_global"]:
        alertas.append(f"COBERTURA GLOBAL: {cov_global}% < {THRESHOLDS['coverage_global']}%")
        verdict = "REJECTED"

    tests = reporte.get("tests", {})
    failed = tests.get("failed", 0)
    if failed > THRESHOLDS["tests_failed_max"]:
        alertas.append(f"TESTS FALLADOS: {failed} > {THRESHOLDS['tests_failed_max']}")
        verdict = "REJECTED"

    lint = reporte.get("lint", {})
    errors = lint.get("errors", 0)
    if errors > THRESHOLDS["lint_errors_max"]:
        alertas.append(f"ERRORES LINT: {errors} > {THRESHOLDS['lint_errors_max']}")
        verdict = "REJECTED"

    security = reporte.get("security", {})
    secrets = security.get("secrets", 0)
    if secrets > THRESHOLDS["secrets_max"]:
        alertas.append(f"SECRETOS: {secrets} > {THRESHOLDS['secrets_max']}")
        verdict = "REJECTED"

    return verdict, alertas


def main():
    reporte = leer_ultimo_reporte()
    if reporte is None:
        print("QUALITY GATE: NO REPORTE ENCONTRADO")
        print("Razon: no hay reportes JSON en data/tuneladora_reports/")
        sys.exit(1)

    verdict, alertas = evaluar(reporte)

    print(f"QUALITY GATE: {verdict}")
    print(f"Reporte: {reporte.get('timestamp', 'N/A')}")
    print(f"Cobertura global: {reporte.get('coverage', {}).get('global', 0)}%")
    print(f"Tests: {reporte.get('tests', {})}")
    print(f"Lint: {reporte.get('lint', {})}")
    print(f"Security: {reporte.get('security', {})}")

    if alertas:
        print("\nAlertas:")
        for a in alertas:
            print(f"  - {a}")

    sys.exit(0 if verdict == "ACCEPTED" else 1)


if __name__ == "__main__":
    main()

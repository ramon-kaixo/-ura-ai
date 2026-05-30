#!/usr/bin/env python3
"""reflexion_profunda.py — Analiza fallos del test de conciencia y propone correcciones."""

import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

TEST_SCRIPT = Path.home() / "URA/ura_ia_1972/scripts/test_conciencia.py"
MCP_URL = "http://127.0.0.1:9091"
SUGERENCIAS = Path("/opt/ura/data/sugerencias.json")
NOTIFICAR = Path("/opt/ura/scripts/notificar.sh")
PROBAR = Path(__file__).resolve().parent.parent / "probar_sugerencia.py"
LOG = Path.home() / "URA/ura_ia_1972/logs/reflexion.log"
LOG.parent.mkdir(parents=True, exist_ok=True)


def log(msg):
    with open(LOG, "a") as f:
        f.write(f"{datetime.now().isoformat()} - {msg}\n")
    print(msg)


def sugerir(problema, solucion):
    sugs = []
    if SUGERENCIAS.exists():
        with open(SUGERENCIAS) as f:
            sugs = json.load(f)
    idx = len(sugs)
    sugs.append(
        {
            "timestamp": time.time(),
            "dominio": "reflexion",
            "problema": problema,
            "solucion": solucion,
        }
    )
    with open(SUGERENCIAS, "w") as f:
        json.dump(sugs, f, indent=2)
    # Probar sin preguntar
    subprocess.Popen([sys.executable, str(PROBAR), str(idx)])


def main():
    log("=== Reflexion profunda ===")

    # Ejecutar test
    log("Ejecutando test de conciencia...")
    r = subprocess.run(
        [sys.executable, str(TEST_SCRIPT)], capture_output=True, text=True, timeout=120
    )

    if r.returncode == 0:
        log("Test superado. Sin acciones necesarias.")
        return 0

    log(f"Test fallado (exit: {r.returncode})")
    log(f"Salida: {r.stdout[:500]}")

    # Analizar causa probable
    output = (r.stdout + r.stderr).lower()

    causas = []
    if "no pued" in output or "no tengo" in output:
        causas.append(("tools no disponibles", "Verificar tools vinculadas a URA en Open WebUI"))
    if "error" in output or "traceback" in output:
        causas.append(("error de ejecucion", "Revisar logs del MCP server en :9091"))
    if "permiso" in output or "denied" in output:
        causas.append(("permisos insuficientes", "Ejecutar conceder_permisos_accesibilidad.sh"))
    if "timeout" in output or "connection" in output:
        causas.append(("servicio no disponible", "Verificar que GX10 y MCP esten activos"))

    if not causas:
        causas.append(("causa desconocida", "Revisar system prompt de URA y function calling"))

    for problema, solucion in causas:
        log(f"  Causa: {problema}")
        sugerir(f"Reflexion: {problema}", solucion)

    if NOTIFICAR.exists():
        subprocess.run([str(NOTIFICAR), f"URA fallo test de conciencia: {causas[0][0]}"])

    return 1


if __name__ == "__main__":
    sys.exit(main())

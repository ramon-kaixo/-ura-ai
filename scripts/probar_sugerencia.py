#!/usr/bin/env python3
"""prueba sugerencias en sandbox, aplica si pasan, rollback si fallan."""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

SUGGESTIONS_FILE = Path("/opt/ura/data/sugerencias.json")
SANDBOX_CONTAINER = "ura-mejora-continua"
NOTIFY_SCRIPT = str(Path(__file__).resolve().parent / "notificar.sh")
LOG = Path.home() / "URA/ura_ia_1972/logs/probar_sugerencia.log"
LOG.parent.mkdir(parents=True, exist_ok=True)


def log(msg):
    with open(LOG, "a") as f:
        f.write(f"{datetime.now().isoformat()} - {msg}\n")
    print(msg)


def aplicar_y_probar(sugerencia):
    dominio = sugerencia.get("dominio", "general")
    solucion = sugerencia.get("solucion", "")
    problema = sugerencia.get("problema", "")

    log(f"Probando sugerencia: {problema}")

    # 1. Snapshot via git stash
    subprocess.run(
        ["docker", "exec", SANDBOX_CONTAINER, "git", "stash"],
        capture_output=True,
        timeout=15,
    )

    # 2. Aplicar la solucion en el sandbox segun el dominio
    if dominio == "reflexion":
        cmd_list = ["docker", "exec", SANDBOX_CONTAINER, "/bin/bash", "-c", solucion]
    else:
        cmd_list = ["docker", "exec", SANDBOX_CONTAINER] + solucion.split()
    try:
        result = subprocess.run(cmd_list, capture_output=True, text=True, timeout=30)
        log(f"Aplicacion: exit={result.returncode}, out={result.stdout[:200]}")
    except subprocess.TimeoutExpired:
        log("Timeout al aplicar solucion")
        tests_ok = False
        return

    # 3. Ejecutar tests en el sandbox
    tests_ok = True
    for test_cmd in [
        "ruff check .",
    ]:
        try:
            r = subprocess.run(
                [
                    "docker",
                    "exec",
                    SANDBOX_CONTAINER,
                    "/bin/bash",
                    "-c",
                    f"cd /workspace && {test_cmd}",
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if r.returncode != 0:
                log(f"Test fallido: {test_cmd}")
                log(f"  salida: {r.stdout[:300]}")
                tests_ok = False
                break
        except subprocess.TimeoutExpired:
            log(f"Timeout en test: {test_cmd}")
            tests_ok = False
            break

    # 4. Si pasa, aplicar en produccion; si no, rollback
    if tests_ok:
        log("Tests pasados. Aplicando en produccion.")
        try:
            subprocess.run(solucion.split(), capture_output=True, text=True, timeout=30)
        except subprocess.TimeoutExpired:
            log("Timeout al aplicar en produccion")
        subprocess.run(
            [NOTIFY_SCRIPT, f"Sugerencia aplicada: {problema}", "info", "all"],
            timeout=10,
        )
        # Disparar autopsia post-resolucion en background
        autopsia_script = str(Path(__file__).resolve().parent / "autopsia_causa_raiz.sh")
        subprocess.Popen(
            ["nohup", "bash", autopsia_script, problema[:200], solucion[:200], dominio],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        log(f"Autopsia post-resolucion lanzada en background: {problema[:60]}")
    else:
        log("Tests fallidos. Rollback.")
        subprocess.run(
            ["docker", "exec", SANDBOX_CONTAINER, "git", "stash", "pop"],
            capture_output=True,
            timeout=15,
        )
        subprocess.run(
            [NOTIFY_SCRIPT, f"Sugerencia fallida: {problema}", "error", "all"],
            timeout=10,
        )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: probar_sugerencia.py <indice>")
        sys.exit(1)

    idx = int(sys.argv[1])

    if not SUGGESTIONS_FILE.exists():
        log(f"Archivo de sugerencias no encontrado: {SUGGESTIONS_FILE}")
        sys.exit(1)

    with open(SUGGESTIONS_FILE) as f:
        sugerencias = json.load(f)

    if idx >= len(sugerencias):
        log(f"Indice {idx} fuera de rango (max {len(sugerencias) - 1})")
        sys.exit(1)

    aplicar_y_probar(sugerencias[idx])

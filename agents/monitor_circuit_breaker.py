#!/usr/bin/env python3
# monitor_circuit_breaker.py – Aísla agentes con fallos consecutivos

import os
import subprocess
import time
import json
from datetime import datetime

REPO = os.environ.get("REPO", os.path.expanduser("~/URA/ura_ia_1972"))
FALLOS_FILE = os.path.join(REPO, "data", "fallos_agentes.json")
CUARENTENA_DIR = os.path.join(REPO, "data", "cuarentena")

UMBRAL_FALLOS = int(os.environ.get("CB_UMBRAL_FALLOS", "10"))
VENTANA_SEGUNDOS = int(os.environ.get("CB_VENTANA_SEGUNDOS", "120"))
NOTIFICAR_SCRIPT = os.path.join(REPO, "scripts", "notificar.sh")
SUGERENCIAS_FILE = os.path.join(REPO, "data", "sugerencias.json")

AGENTES = [
    "observador_codigo.py",
    "auditoria_red.py",
    "camara_analizador.py",
    "actualizador_check.py",
    "rollback_long_term.py",
    "agente_backup.py",
    "scheduler_orchestrator.py",
    "monitor_pagos.py",
    "escaneo_red.py",
    "mejora_continua.py",
    "canary_deployer.py",
    "rl_suggester.py",
    "deploy_patches.py",
    "telegram_bot.py",
    "centinela.py",
    "vision_monitor.py",
    "orquestador.py",
    "mantenimiento.py",
    "openclaw_bridge.py",
    "health_api.py",
    "whatsapp_bot.js",
    "monitor_proactivo.py",
    "analizador_proactivo.py",
    "camaras.py",
    "tpv_agent.py",
    "voz_local.sh",
]


def cargar_fallos():
    if os.path.exists(FALLOS_FILE):
        with open(FALLOS_FILE) as f:
            return json.load(f)
    return {}


def guardar_fallos(data):
    with open(FALLOS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def esta_en_cuarentena(agente):
    return os.path.exists(os.path.join(CUARENTENA_DIR, f"{agente}.lock"))


def verificar_agente(agente):
    result = subprocess.run(["pgrep", "-f", agente], capture_output=True)
    return result.returncode == 0


def notificar(mensaje):
    if os.path.exists(NOTIFICAR_SCRIPT):
        subprocess.run([NOTIFICAR_SCRIPT, mensaje])


def agregar_sugerencia(problema, solucion):
    sugerencias = []
    if os.path.exists(SUGERENCIAS_FILE):
        with open(SUGERENCIAS_FILE) as f:
            sugerencias = json.load(f)
    sugerencias.append(
        {
            "timestamp": time.time(),
            "dominio": "circuit_breaker",
            "problema": problema,
            "solucion": solucion,
            "gravedad": "alta",
        }
    )
    if len(sugerencias) > 200:
        sugerencias = sugerencias[-200:]
    with open(SUGERENCIAS_FILE, "w") as f:
        json.dump(sugerencias, f, indent=2)


def main():
    os.makedirs(CUARENTENA_DIR, exist_ok=True)
    fallos = cargar_fallos()
    ahora = time.time()

    for agente in AGENTES:
        if esta_en_cuarentena(agente):
            continue

        vivo = verificar_agente(agente)
        if not vivo:
            fallos.setdefault(agente, []).append(ahora)
            fallos[agente] = [t for t in fallos[agente] if ahora - t <= VENTANA_SEGUNDOS]
            if len(fallos[agente]) >= UMBRAL_FALLOS:
                lock_file = os.path.join(CUARENTENA_DIR, f"{agente}.lock")
                with open(lock_file, "w") as f:
                    f.write(f"Aislado por {UMBRAL_FALLOS} fallos en {VENTANA_SEGUNDOS}s\n")
                    f.write(f"Fecha: {datetime.now().isoformat()}\n")
                subprocess.run(["pkill", "-f", agente], capture_output=True)
                notificar(f"Agente {agente} aislado por fallos repetidos")
                agregar_sugerencia(
                    f"Agente {agente} aislado por {UMBRAL_FALLOS} fallos en {VENTANA_SEGUNDOS}s",
                    f"Revisar logs y luego eliminar {lock_file} para reactivar",
                )
                fallos[agente] = []

    guardar_fallos(fallos)


if __name__ == "__main__":
    main()

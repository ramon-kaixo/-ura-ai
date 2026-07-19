#!/usr/bin/env python3
"""analizar_fallo_conciencia.py — Analiza resultados del test de conciencia
y ejecuta acciones correctivas automaticas.

Flujo:
1. Ejecuta test_conciencia.py
2. Si falla, determina la causa probable
3. Intenta corregirla (permisos, tools, system prompt)
4. Si no puede, notifica al instalador
"""

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(Path("~/URA/ura_ia_1972").expanduser())
SUGERENCIAS = Path("/opt/ura/data/sugerencias.json")
NOTIFICAR = Path("/opt/ura/scripts/notificar.sh")
LOG = REPO / "logs/conciencia.log"

FALLOS_CONOCIDOS = {
    "teclado": {
        "sintomas": [
            "no puede tocar el teclado",
            "permisos de accesibilidad",
            "pyautogui",
            "pynput",
        ],
        "solucion": "Otorgar permisos de accesibilidad en macOS: System Preferences > Security > Accessibility",
        "script": str(REPO / "scripts/pro" / "conceder_permisos_accesibilidad.sh"),
    },
    "tools": {
        "sintomas": ["no tengo herramientas", "no puedo ejecutar", "no esta disponible"],
        "solucion": "Vincular tools al modelo URA en Open WebUI: Workspace > Models > URA > Tools",
        "script": None,
    },
    "function_calling": {
        "sintomas": ["no puedo usar", "no tengo acceso a"],
        "solucion": "Activar Function Calling en Open WebUI: Admin > Settings > Models",
        "script": None,
    },
}


def log(mensaje) -> None:
    with open(LOG, "a") as f:  # noqa: PTH123
        f.write(f"{datetime.now(UTC).isoformat()} - {mensaje}\n")


def agregar_sugerencia(problema, solucion) -> None:
    sugerencias = []
    if SUGERENCIAS.exists():
        with open(SUGERENCIAS) as f:  # noqa: PTH123
            sugerencias = json.load(f)
    sugerencias.append(
        {
            "timestamp": datetime.now(UTC).timestamp(),
            "dominio": "conciencia",
            "problema": problema,
            "solucion": solucion,
            "gravedad": "alta",
        },
    )
    with open(SUGERENCIAS, "w") as f:  # noqa: PTH123
        json.dump(sugerencias, f, indent=2)


def notificar(mensaje) -> None:
    if NOTIFICAR.exists():
        subprocess.run([str(NOTIFICAR), mensaje], check=False)  # noqa: S603


def diagnosticar_y_corregir() -> bool:
    """Ejecuta el test, analiza fallos, intenta corregir."""
    log("=== Inicio analisis de conciencia ===")

    # 1. Ejecutar test
    log("Ejecutando test de conciencia...")
    result = subprocess.run(  # noqa: S603
        [sys.executable, str(REPO / "scripts/test_conciencia.py")],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    test_output = result.stdout + result.stderr

    if result.returncode == 0:
        log("Test de conciencia SUPERADO")
        return True

    log(f"Test FALLADO (exit: {result.returncode})")
    log(f"Salida: {test_output[:500]}")

    # 2. Diagnosticar causa
    fallos_detectados = []
    for fallo, info in FALLOS_CONOCIDOS.items():
        for sintoma in info["sintomas"]:
            if sintoma.lower() in test_output.lower():
                fallos_detectados.append(fallo)
                log(f"Fallo detectado: {fallo} — {info['solucion']}")
                break

    if not fallos_detectados:
        log("Fallo no clasificado. Notificando al administrador.")
        agregar_sugerencia(
            "Test de conciencia fallo por causa desconocida",
            "Revisar logs del test y configuracion de URA en Open WebUI",
        )
        notificar("URA fallo el test de conciencia sin causa identificada")
        return False

    # 3. Intentar correccion
    for fallo in fallos_detectados:
        info = FALLOS_CONOCIDOS[fallo]
        if info["script"] and Path(info["script"]).exists():
            log(f"Ejecutando script corrector para '{fallo}': {info['script']}")
            try:
                subprocess.run(["bash", info["script"]], capture_output=True, text=True, timeout=30, check=False)  # noqa: S603, S607
                log(f"Correccion aplicada para '{fallo}'")
            except Exception as e:
                log(f"Error ejecutando correccion '{fallo}': {e}")
                agregar_sugerencia(f"Fallo al corregir '{fallo}'", info["solucion"])
                notificar(f"Fallo al corregir '{fallo}' en URA")
        else:
            log(f"No hay script de correccion para '{fallo}'. Notificando.")
            agregar_sugerencia(f"Fallo de conciencia: {fallo}", info["solucion"])
            notificar(f"URA necesita correccion manual: {fallo}")

    return False


if __name__ == "__main__":
    sys.exit(0 if diagnosticar_y_corregir() else 1)

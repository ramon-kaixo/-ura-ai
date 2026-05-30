#!/usr/bin/env python3
"""meta_mejora.py — URA mejora su propio prompt basandose en reflexiones."""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REFLEXIONES = Path("/opt/ura/data/reflexiones.log")
MEJORAS = Path("/opt/ura/config/prompts/mejoras.txt")
SUGERENCIAS = Path("/opt/ura/data/sugerencias.json")
PROBAR = Path(__file__).resolve().parent.parent / "probar_sugerencia.py"


def analizar_reflexiones():
    if not REFLEXIONES.exists():
        return

    with open(REFLEXIONES) as f:
        lineas = f.readlines()

    if len(lineas) < 3:
        return  # Necesita minimo 3 reflexiones para analizar

    print(f"Analizando {len(lineas)} reflexiones...")

    # Detectar patrones
    fallos = sum(1 for l in lineas if "fallo" in l.lower())
    exitos = sum(1 for l in lineas if "exitoso" in l.lower() or "exito" in l.lower())

    sugerencia = f"Analisis de {len(lineas)} reflexiones: {exitos} exitos, {fallos} fallos."
    print(sugerencia)

    if fallos > exitos * 2:
        sugerencia += " Hay muchos fallos. Revisar tools, permisos y function calling."
        # Registrar sugerencia
        sugs = []
        if SUGERENCIAS.exists():
            with open(SUGERENCIAS) as f:
                sugs = json.load(f)
        idx = len(sugs)
        sugs.append(
            {
                "timestamp": datetime.now().timestamp(),
                "dominio": "meta_mejora",
                "problema": "Exceso de fallos en acciones de URA",
                "solucion": "Revisar configuracion de tools, function calling en Open WebUI, y permisos de accesibilidad macOS",
            }
        )
        with open(SUGERENCIAS, "w") as f:
            json.dump(sugs, f, indent=2)
        subprocess.Popen([sys.executable, str(PROBAR), str(idx)])

    # Guardar mejora
    MEJORAS.parent.mkdir(parents=True, exist_ok=True)
    with open(MEJORAS, "a") as f:
        f.write(f"\n# {datetime.now().isoformat()}\n# {sugerencia}\n")


if __name__ == "__main__":
    analizar_reflexiones()

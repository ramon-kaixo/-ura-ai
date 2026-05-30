#!/usr/bin/env python3
"""reflexion_ura.py — URA reflexiona sobre sus propias acciones y evalua su desempeno."""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

LOG_DIR = Path("/opt/ura/data")
MONOLOGO = LOG_DIR / "monologo_interno.json"
REFLEXIONES = LOG_DIR / "reflexiones.log"
ACCIONES = LOG_DIR / "cola_acciones.json"
SUGERENCIAS = Path("/opt/ura/data/sugerencias.json")

LOG_DIR.mkdir(parents=True, exist_ok=True)


def cargar_acciones(limite=10):
    if ACCIONES.exists():
        with open(ACCIONES) as f:
            return json.load(f)[-limite:]
    return []


def registrar_reflexion(texto):
    with open(REFLEXIONES, "a") as f:
        f.write(f"{datetime.now().isoformat()} - {texto}\n")


PROBAR = Path(__file__).resolve().parent.parent / "probar_sugerencia.py"


def agregar_sugerencia(problema, solucion):
    sugerencias = []
    if SUGERENCIAS.exists():
        with open(SUGERENCIAS) as f:
            sugerencias = json.load(f)
    idx = len(sugerencias)
    sugerencias.append(
        {
            "timestamp": datetime.now().timestamp(),
            "dominio": "reflexion",
            "problema": problema,
            "solucion": solucion,
        }
    )
    with open(SUGERENCIAS, "w") as f:
        json.dump(sugerencias, f, indent=2)
    subprocess.Popen([sys.executable, str(PROBAR), str(idx)])


def reflexionar():
    acciones = cargar_acciones()
    if not acciones:
        registrar_reflexion("Sin acciones recientes para reflexionar")
        return

    # Analizar acciones
    exitosos = sum(1 for a in acciones if a.get("ok", False))
    fallidos = sum(1 for a in acciones if not a.get("ok", True))
    tipos = {}
    for a in acciones:
        tipo = a.get("tipo", "desconocido")
        tipos[tipo] = tipos.get(tipo, 0) + 1

    reflexion = (
        f"Analisis de las ultimas {len(acciones)} acciones: "
        f"{exitosos} exitosas, {fallidos} fallidas. "
        f"Tipos: {', '.join(f'{k}={v}' for k, v in tipos.items())}. "
    )

    if fallidos > exitosos:
        reflexion += "Hay mas fallos que aciertos. Revisar tools y permisos."
        agregar_sugerencia(
            "Tasa de fallos alta en acciones",
            "Revisar herramientas MCP/API y permisos de accesibilidad",
        )
    else:
        reflexion += "Proporcion aceptable. Sin cambios necesarios."

    registrar_reflexion(reflexion)
    print(reflexion)


if __name__ == "__main__":
    reflexionar()

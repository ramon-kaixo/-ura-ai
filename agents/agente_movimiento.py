#!/usr/bin/env python3
"""agente_movimiento.py — Mueve archivos a cuarentena en lugar de borrarlos."""

import os
import shutil
import sys
import time
from datetime import datetime

CUARENTENA = "/opt/ura/cuarentena"


def mover(origen):
    origen = os.path.abspath(os.path.expanduser(origen))
    if not os.path.exists(origen):
        return f"No existe: {origen}"
    os.makedirs(CUARENTENA, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre = os.path.basename(origen)
    destino = os.path.join(CUARENTENA, f"{ts}_{nombre}")
    try:
        shutil.move(origen, destino)
        # Metadata
        meta = os.path.join(CUARENTENA, f"{ts}_{nombre}.meta")
        with open(meta, "w") as f:
            f.write(f"origen={origen}\ntimestamp={time.time()}\n")
        return f"MOVED: {origen} -> {destino}"
    except Exception as e:
        return f"Error: {e}"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("USO: agente_movimiento.py <archivo>")
        sys.exit(1)
    print(mover(sys.argv[1]))

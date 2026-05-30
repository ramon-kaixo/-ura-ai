#!/usr/bin/env python3
"""agente_validacion.py — Cuarto Agente de Seguridad.
Calcula hash SHA-256 antes de modificaciones. Bloquea si permisos invalidos."""

import hashlib
import os
import shutil
import sys
from datetime import datetime

CUARENTENA = "/opt/ura/cuarentena"
os.makedirs(CUARENTENA, exist_ok=True)


def validar(ruta):
    if not os.path.exists(ruta):
        return False, "Archivo no existe"
    with open(ruta, "rb") as f:
        hash_pre = hashlib.sha256(f.read()).hexdigest()
    if not os.access(ruta, os.W_OK):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = os.path.join(CUARENTENA, f"{ts}_{os.path.basename(ruta)}")
        shutil.copy2(ruta, dest)
        with open(dest + ".meta", "w") as m:
            m.write(f"origen={ruta}\nmotivo=permisos\nhash={hash_pre}\n")
        return False, f"Sin permisos. Backup en {dest}"
    return True, hash_pre


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("USO: agente_validacion.py <archivo>")
        sys.exit(1)
    ok, msg = validar(sys.argv[1])
    print(f"{'OK:' if ok else 'ERROR:'}{msg}")
    sys.exit(0 if ok else 1)

#!/usr/bin/env python3
"""PLUGIN_TEMPLATE — Copiar y modificar para crear un script nuevo.

PASOS:
  1. Copiar: cp PLUGIN_TEMPLATE.py mi_nuevo_script.py
  2. Editar: cambiar nombre, fase, timeout, args
  3. Implementar: escribir la lógica en main()
  4. Listo: tuneladora_mejora lo descubre solo

FASES DISPONIBLES:
  "pre"      — Antes del refactor (validación, snapshots)
  "refactor" — Durante el refactor (poda, transformación)
  "post"     — Después del refactor (validación, auto-reglas)
  "always"   — Se ejecuta siempre (independiente de fase)
"""

import subprocess
from datetime import datetime
from pathlib import Path

# ══════════════════════════════════════════════════════════════
# PLUGIN METADATA — Editar esta sección
# ══════════════════════════════════════════════════════════════

PLUGIN = {
    "name": "mi_nuevo_script",        # Nombre único del plugin
    "phase": "post",                   # pre | refactor | post | always
    "timeout": 30,                     # Timeout en segundos
    "args": ["--json"],                # Argumentos fijos al ejecutar
    "blocking": False,                 # True = aborta si falla
    "needs_file": True,                # True = recibe archivo como argumento
}

# ══════════════════════════════════════════════════════════════
# IMPLEMENTACIÓN — Editar esta sección
# ══════════════════════════════════════════════════════════════

URA_ROOT = Path(__file__).parent.parent.parent


def log(msg) -> None:
    pass


def run(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(URA_ROOT))
        return r.returncode, r.stdout, r.stderr
    except Exception as e:
        return -1, "", str(e)


def mi_logica(archivo=None):
    """Implementar la lógica del script aquí."""
    log("  Ejecutando mi_nuevo_script...")
    if archivo:
        log(f"  Archivo: {archivo}")

    # Tu código aquí
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=PLUGIN["name"])
    parser.add_argument("archivo", nargs="?", help="Archivo a procesar")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = mi_logica(args.archivo)

    if args.json:
        pass
    else:
        log(f"  Resultado: {result.get('status', '?')}")


if __name__ == "__main__":
    main()

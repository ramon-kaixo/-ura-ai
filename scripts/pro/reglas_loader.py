#!/usr/bin/env python3
"""Reglas Loader desde JSON."""

import json
import os
from pathlib import Path

REGLAS_PATH = Path(os.environ.get("REGLAS_PATH", ".nervioso/reglas_auto.json"))


def _cargar_reglas_builtin() -> list:
    config_path = Path(os.environ.get("REGLAS_CONFIG", "config/reglas_builtin.json"))
    if config_path.exists():
        try:
            data = json.loads(config_path.read_text())
            return data.get("reglas_builtin", [])
        except Exception:
            return _reglas_fallback()
    return _reglas_fallback()


def _reglas_fallback() -> list:
    return [
        {
            "id": "builtin_fix_import_os",
            "patron": "F821",
            "accion": "añadir_import",
            "parametros": {"import": "import os"},
            "confianza": 0.95,
            "origen": "built-in",
        },
    ]


PREDEFINED_RULES = _cargar_reglas_builtin()


def _reglas_fallback() -> list:
    return [
        {
            "id": "builtin_fix_import_os",
            "patron": "F821",
            "accion": "añadir_import",
            "parametros": {"import": "import os"},
            "confianza": 0.95,
            "origen": "built-in",
        },
    ]


def cargar_reglas() -> dict:
    if REGLAS_PATH.exists():
        try:
            return json.loads(REGLAS_PATH.read_text())
        except Exception:
            pass
    return {"reglas": list(PREDEFINED_RULES), "ultima_actualizacion": ""}


def guardar_reglas(data: dict) -> None:
    REGLAS_PATH.parent.mkdir(parents=True, exist_ok=True)
    REGLAS_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

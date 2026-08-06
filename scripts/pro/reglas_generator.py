#!/usr/bin/env python3
"""Reglas Generator — Auto-aprendizaje desde patrones."""

import json
import os
import re
import sys
import time
from pathlib import Path

# Import from loader in same directory
_sys_path = Path(Path(__file__).resolve().parent)
if _sys_path not in sys.path:
    sys.path.insert(0, _sys_path)

REGLAS_PATH = Path(os.environ.get("REGLAS_PATH", ".nervioso/reglas_auto.json"))
WATERMARKS_PATH = Path(os.environ.get("WATERMARKS_PATH", ".nervioso/watermarks.json"))

import contextlib

from reglas_loader import cargar_reglas, guardar_reglas

# guardar_reglas imported from reglas_loader


def _extraer_nombre_f821(mensaje: str) -> str | None:
    """Extrae el nombre del símbolo no definido de un mensaje F821."""
    m = re.search(r"Undefined name `([^`]+)`", mensaje)
    return m.group(1) if m else None


def _es_import_estandar(nombre: str) -> dict | None:
    config_path = Path(os.environ.get("REGLAS_CONFIG", "config/reglas_builtin.json"))
    if config_path.exists():
        try:
            data = json.loads(config_path.read_text())
            return data.get("imports_estandar", {}).get(nombre)
        except Exception:  # noqa: S110
            pass
    return None


def generar_reglas_desde_patrones(watermarks: dict) -> list[dict]:
    """Genera reglas automáticas desde patrones sistémicos."""
    reglas_nuevas = []
    existentes = cargar_reglas()
    ids_existentes = {r["id"] for r in existentes.get("reglas", [])}

    for patron in watermarks.get("patrones_sistemicos", []):
        tipo = patron.get("tipo", "")
        mensaje = patron.get("mensaje", "")
        apariciones = patron.get("apariciones", 0)
        archivos = patron.get("archivos", [])

        if apariciones < 3:
            continue

        if tipo == "F821":
            nombre = _extraer_nombre_f821(mensaje)
            if nombre:
                # Verificar import estándar
                import_info = _es_import_estandar(nombre)
                if import_info:
                    rule_id = f"auto_fix_{nombre}_{int(time.time())}"
                    if rule_id not in ids_existentes:
                        reglas_nuevas.append(
                            {
                                "id": rule_id,
                                "patron": mensaje,
                                "tipo": tipo,
                                "accion": import_info["accion"],
                                "parametros": import_info["params"],
                                "confianza": min(0.5 + apariciones * 0.1, 0.95),
                                "origen": "auto",
                                "veces_aplicado": 0,
                                "veces_exitoso": 0,
                                "creado": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                "archivos_ejemplo": archivos[:5],
                            },
                        )
                        ids_existentes.add(rule_id)

    return reglas_nuevas


def actualizar_reglas():
    """Actualiza reglas desde watermarks y guarda."""
    # Cargar watermarks
    data_watermarks = {"patrones_sistemicos": []}
    if WATERMARKS_PATH.exists():
        with contextlib.suppress(Exception):
            data_watermarks = json.loads(WATERMARKS_PATH.read_text())

    # Generar nuevas reglas
    nuevas = generar_reglas_desde_patrones(data_watermarks)

    # Cargar y actualizar
    data_reglas = cargar_reglas()

    if nuevas:
        data_reglas["reglas"].extend(nuevas)

    # Ordenar por confianza descendente
    data_reglas["reglas"].sort(key=lambda r: -r.get("confianza", 0))
    data_reglas["ultima_actualizacion"] = time.strftime("%Y-%m-%dT%H:%M:%S")

    guardar_reglas(data_reglas)
    return data_reglas

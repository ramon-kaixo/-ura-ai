#!/usr/bin/env python3
"""Reglas Applier — Aplica reparaciones deterministas."""

import json
import os
import re
import subprocess
from pathlib import Path

REGLAS_PATH = Path(os.environ.get("REGLAS_PATH", ".nervioso/reglas_auto.json"))


def detectar_f821_en_codigo(codigo: str, archivo: str) -> list[dict]:
    """Detecta F821 en código usando ruff (rápido) o AST fallback."""
    try:
        r = subprocess.run(
            ["ruff", "check", "--select", "F821", "--output-format", "json", "-"],  # noqa: S607
            input=codigo,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if r.stdout.strip():
            try:
                resultados = json.loads(r.stdout)
                return [
                    {
                        "linea": x.get("location", {}).get("row", 0),
                        "col": x.get("location", {}).get("column", 0),
                        "mensaje": x.get("message", ""),
                        "codigo": x.get("code", "F821"),
                    }
                    for x in resultados
                ]
            except json.JSONDecodeError:
                pass
    except Exception:  # noqa: S110
        pass
    return []


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


def aplicar_regla_a_codigo(codigo: str, regla: dict) -> tuple[str, bool]:  # noqa: C901, PLR0911, PLR0912
    """Aplica una regla de reparación al código.

    Returns:
        (codigo_reparado, aplicado_con_exito)

    """
    accion = regla.get("accion", "")
    params = regla.get("parametros", {})

    if accion == "ignorar":
        return codigo, False

    if accion == "añadir_import":
        import_stmt = params.get("import", "")
        if not import_stmt:
            return codigo, False
        # Verificar si ya existe
        if import_stmt in codigo:
            return codigo, False
        # Añadir después del primer bloque de imports
        lines = codigo.splitlines()
        insert_at = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith(("import ", "from ")):
                insert_at = i + 1
            elif (
                stripped
                and not stripped.startswith("#")
                and not stripped.startswith('"""')
                and not stripped.startswith("'''")
            ):
                break
        lines.insert(insert_at, import_stmt)
        return "\n".join(lines), True

    if accion == "añadir_import_from":
        from_mod = params.get("from", "")
        import_name = params.get("import", "")
        if not from_mod or not import_name:
            return codigo, False
        stmt = f"from {from_mod} import {import_name}"
        if stmt in codigo:
            return codigo, False

        lines = codigo.splitlines()
        insert_at = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith(("import ", "from ")):
                insert_at = i + 1
            elif (
                stripped
                and not stripped.startswith("#")
                and not stripped.startswith('"""')
                and not stripped.startswith("'''")
            ):
                break
        lines.insert(insert_at, stmt)
        return "\n".join(lines), True

    return codigo, False

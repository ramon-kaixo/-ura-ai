#!/usr/bin/env python3
# PLUGIN METADATA
PLUGIN = {
    "name": "auto_reglas",
    "phase": "post",
    "timeout": 30,
    "args": ["--generar"],
    "blocking": False,
    "needs_file": False,
}
"""Auto-Reglas — Sistema de reparación auto-aprendida.
Orquestador que importa de módulos: loader, applier, generator.
"""

import ast
import os
import sys
from pathlib import Path

# Importar desde módulos especializados
_sys_path = Path(Path(__file__).resolve().parent)
if _sys_path not in sys.path:
    sys.path.insert(0, _sys_path)

from reglas_applier import aplicar_regla_a_codigo
from reglas_generator import actualizar_reglas
from reglas_loader import cargar_reglas, guardar_reglas

WATERMARKS_PATH = Path(os.environ.get("WATERMARKS_PATH", ".nervioso/watermarks.json"))


def aplicar_reglas_a_archivo(ruta) -> dict:
    if isinstance(ruta, str):
        ruta = Path(ruta)
    """Aplica todas las reglas aplicables a un archivo."""
    data = cargar_reglas()
    reglas = data.get("reglas", [])
    codigo = ruta.read_text(encoding="utf-8")
    aplicadas = []
    errores = []

    for regla in reglas:
        confianza = regla.get("confianza", 0)
        if confianza < 0.5:
            continue  # Saltar reglas de baja confianza

        codigo_nuevo, aplicado = aplicar_regla_a_codigo(codigo, regla)
        if aplicado:
            # Verificar que el código siga compilando
            try:
                compile(codigo_nuevo, str(ruta), "exec")
                codigo = codigo_nuevo
                aplicadas.append(regla["id"])
                regla["veces_aplicado"] = regla.get("veces_aplicado", 0) + 1
                regla["veces_exitoso"] = regla.get("veces_exitoso", 0) + 1
            except SyntaxError as e:
                errores.append(f"{regla['id']}: {e}")
                regla["veces_aplicado"] = regla.get("veces_aplicado", 0) + 1

    # Escribir si hubo cambios
    if aplicadas:
        ruta.write_text(codigo, encoding="utf-8")
        guardar_reglas(data)

    return {
        "archivo": str(ruta),
        "reglas_aplicadas": aplicadas,
        "reglas_con_error": errores,
        "total_reglas": len(reglas),
    }


def estado() -> dict:
    data = cargar_reglas()
    reglas = data.get("reglas", [])
    activas = [r for r in reglas if r.get("confianza", 0) >= 0.5]
    aprendidas = [r for r in reglas if r.get("origen") == "auto"]
    builtin = [r for r in reglas if r.get("origen") == "built-in"]

    return {
        "total_reglas": len(reglas),
        "activas": len(activas),
        "builtin": len(builtin),
        "auto_aprendidas": len(aprendidas),
        "ultima_actualizacion": data.get("ultima_actualizacion", ""),
        "por_tipo": dict(__import__("collections").Counter(r.get("tipo", "?") for r in reglas)),
    }


def scan_project() -> None:
    """Escanear todo el proyecto."""
    URA_ROOT = Path("/home/ramon/URA/ura_ia_1972")
    results = {}
    for py_file in URA_ROOT.rglob("*.py"):
        p = str(py_file)
        if any(
            x in p
            for x in ["/.venv/", "/.git/", "/__pycache__/", "/backups/", "/site-packages/", "/scripts_eliminados/"]
        ):
            continue
        try:
            content = py_file.read_text()
            ast.parse(content)
            results[p] = {"status": "parsed_ok"}
        except SyntaxError:
            results[p] = {"status": "syntax_error"}
        except Exception:
            results[p] = {"status": "error"}


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Auto-Reglas de reparación")
    parser.add_argument("--generar", action="store_true", help="Generar reglas desde patrones")
    parser.add_argument("--aplicar", type=str, help="Aplicar reglas a un archivo")
    parser.add_argument("--estado", action="store_true", help="Ver reglas activas")
    parser.add_argument("--scan", action="store_true", help="Escanear todo el proyecto")
    parser.add_argument("--json", action="store_true", help="Salida JSON")
    args = parser.parse_args()

    if args.scan:
        scan_project()
        return

    if args.generar:
        actualizar_reglas()

    if args.aplicar:
        ruta = Path(args.aplicar)
        if not ruta.exists():
            sys.exit(1)
        resultado = aplicar_reglas_a_archivo(ruta)
        if args.json:
            pass
        else:
            for _r in resultado["reglas_aplicadas"]:
                pass
            for _r in resultado["reglas_con_error"]:
                pass

    if args.estado or not (args.generar or args.aplicar):
        e = estado()
        if args.json:
            pass
        elif e["por_tipo"]:
            for _t, _n in e["por_tipo"].items():
                pass


if __name__ == "__main__":
    main()

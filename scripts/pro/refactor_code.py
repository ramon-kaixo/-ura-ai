#!/usr/bin/env python3
"""Refactorización automática del código URA"""

import ast
import os
import shutil
from pathlib import Path
from typing import Any

URA_ROOT = os.environ.get("URA_ROOT", os.path.expanduser("~/URA/ura_ia_1972"))
CHANGES = []


def log(msg: str) -> None:
    CHANGES.append(msg)
    print(msg)


def remove_dead_code() -> int:
    """Elimina funciones/variables muertas detectadas por patrón AST"""
    removed = 0
    for py_file in Path(URA_ROOT).rglob("*.py"):
        py_path = str(py_file)
        if any(
            excl in py_path
            for excl in [
                "/venv/",
                "/.git/",
                "/.mypy_cache/",
                "/__pycache__/",
                "/.tox/",
                "/node_modules/",
            ]
        ):
            continue
        try:
            with open(py_file) as f:
                source = f.read()
            tree = ast.parse(source)
            # Buscar funciones que solo se llaman a sí mismas (recursión sin uso externo)
            defined_funcs = {
                node.name
                for node in ast.walk(tree)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
            called_funcs = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    called_funcs.add(node.func.id)
                elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                    called_funcs.add(f"{node.value.id}.{node.attr}")
            unused = defined_funcs - called_funcs
            # Filtrar dunder methods y callbacks comunes
            unused = {
                f
                for f in unused
                if not f.startswith("__")
                and f
                not in {
                    "main",
                    "setup",
                    "run",
                    "start",
                    "stop",
                    "init",
                    "cleanup",
                    "configure",
                    "get_instance",
                }
            }
            if unused:
                log(f"  ⚠️  {py_path}: funciones sin referencia: {', '.join(sorted(unused))[:120]}")
                removed += len(unused)
        except (SyntaxError, UnicodeDecodeError):
            pass
    return removed


def consolidate_duplicate_imports() -> int:
    """Agrupa imports duplicados en un solo archivo"""
    cleaned = 0
    for py_file in Path(URA_ROOT).rglob("*.py"):
        py_path = str(py_file)
        if any(
            excl in py_path
            for excl in [
                "/venv/",
                "/.git/",
                "/.mypy_cache/",
                "/__pycache__/",
                "/.tox/",
                "/node_modules/",
            ]
        ):
            continue
        try:
            with open(py_file) as f:
                lines = f.readlines()
            new_lines: list[str] = []
            seen_imports: set[str] = set()
            changed = False
            for line in lines:
                stripped = line.strip()
                if (
                    stripped.startswith(("import ", "from "))
                    and "#" not in stripped.split("import", 1)[0]
                ):
                    normalized = stripped.split("#")[0].strip()
                    if normalized in seen_imports:
                        changed = True
                        continue
                    seen_imports.add(normalized)
                new_lines.append(line)
            if changed:
                with open(py_file, "w") as f:
                    f.writelines(new_lines)
                cleaned += 1
                log(f"  ✅ {py_path}: imports duplicados eliminados")
        except (UnicodeDecodeError, OSError):
            pass
    return cleaned


def report_large_functions(threshold: int = 80) -> list[dict[str, Any]]:
    """Reporta funciones que superan el umbral de líneas"""
    large: list[dict[str, Any]] = []
    for py_file in Path(URA_ROOT).rglob("*.py"):
        py_path = str(py_file)
        if any(
            excl in py_path
            for excl in [
                "/venv/",
                "/.git/",
                "/.mypy_cache/",
                "/__pycache__/",
                "/.tox/",
                "/node_modules/",
            ]
        ):
            continue
        try:
            with open(py_file) as f:
                source = f.read()
            tree = ast.parse(source)
            with open(py_file) as f:
                lines = f.readlines()
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if hasattr(node, "end_lineno") and node.end_lineno and node.lineno:
                        n_lines = node.end_lineno - node.lineno
                        if n_lines > threshold:
                            large.append({"file": py_path, "function": node.name, "lines": n_lines})
        except (SyntaxError, UnicodeDecodeError):
            pass
    return large


def main() -> None:
    import time

    start = time.time()
    log("🚀 Refactorización automática de código URA")
    log(f"📁 Root: {URA_ROOT}")
    log("")

    # Paso 1: Consolidar imports duplicados
    log("📍 Paso 1: Consolidar imports duplicados")
    cleaned = consolidate_duplicate_imports()
    log(f"   → {cleaned} archivos limpiados")
    log("")

    # Paso 2: Detectar código muerto
    log("📍 Paso 2: Detectar funciones sin referencia")
    removed = remove_dead_code()
    log(f"   → {removed} funciones candidatas a revisión")
    log("")

    # Paso 3: Reportar funciones grandes
    log("📍 Paso 3: Funciones grandes (>80 líneas)")
    large = report_large_functions()
    for f in large[:20]:
        log(f"  📏 {f['file']}:{f['function']} ({f['lines']} líneas)")
    if len(large) > 20:
        log(f"  ... y {len(large) - 20} más")
    log(f"   → {len(large)} funciones grandes detectadas")
    log("")

    elapsed = time.time() - start
    log(f"✅ Refactorización completada en {elapsed:.1f}s")
    if CHANGES:
        log(f"📝 {len([c for c in CHANGES if '✅' in c]) - 2} archivos modificados")


if __name__ == "__main__":
    main()

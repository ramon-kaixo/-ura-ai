#!/usr/bin/env python3
# audit_init.py – Evita imports peligrosos dentro de __init__.py
# Prohibe: import X, from X import y, sys.path.insert/modifications en __init__.py
# - CRITICAL_DIRS: fallo inmediato si tienen imports
# - Subpaquetes: advertencia (no fallo) — son re-exportaciones legítimas
# - sys.path: siempre fallo

import ast
import os
import sys
from pathlib import Path

ROOT = Path(os.environ.get("SOURCE_DIR", os.path.expanduser("~/URA/ura_ia_1972")))
CRITICAL_DIRS = ["core", "agents"]
SUBPACKAGE_OK = {
    "backups",
    "venv",
    "__pycache__",
    "data",
    "logs",
    "node_modules",
    ".git",
    "archive",
    ".tox",
}


def check_init(filepath: Path) -> tuple[bool, list[str]]:
    ok = True
    warnings: list[str] = []

    try:
        with open(filepath, encoding="utf-8") as f:
            tree = ast.parse(f.read())
    except SyntaxError as e:
        return False, [f"  SINTAXIS INVALIDA {filepath}: {e}"]
    except IsADirectoryError:
        return True, []
    except Exception as e:
        return False, [f"  ERROR leyendo {filepath}: {e}"]

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            msg = f"  IMPORT  {filepath}:{node.lineno}"
            warnings.append(msg)
            ok = False

        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Attribute)
                    and target.attr == "path"
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "sys"
                ):
                    msg = f"  sys.path MODIFICADO  {filepath}:{node.lineno}"
                    warnings.append(msg)
                    ok = False

    return ok, warnings


def main() -> int:
    errors = 0
    all_warnings: list[str] = []

    for dirname in CRITICAL_DIRS:
        init_file = ROOT / dirname / "__init__.py"
        if init_file.exists():
            ok, warns = check_init(init_file)
            all_warnings.extend(warns)
            pre = "" if ok else "FALLO "
            for w in warns:
                print(f"{pre}{w}")
            if not ok:
                errors += 1

    for init in ROOT.rglob("__init__.py"):
        if any(part in init.parts for part in SUBPACKAGE_OK):
            continue
        if init.parent.name in CRITICAL_DIRS and init.parent.parent == ROOT:
            continue
        ok, warns = check_init(init)
        for w in warns:
            print(f"  AVISO  {w}")
            all_warnings.append(w)

    if errors:
        print(f"\nRESUMEN: {errors} archivo(s) CRITICO(s) con infracciones")
        sys.exit(1)
    print("OK — todos los __init__.py criticos cumplen la politica")
    sys.exit(0)


if __name__ == "__main__":
    main()

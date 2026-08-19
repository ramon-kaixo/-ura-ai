#!/usr/bin/env python3
"""Gate de sintaxis: verifica que todos los .py modificados en el árbol parsean.

Uso:
  python3 scripts/pro/check_changed_syntax.py          # solo archivos modificados (git)
  python3 scripts/pro/check_changed_syntax.py --all    # todo el repo

Exit 0 si todo parsea, 1 si hay algún SyntaxError (con ruta y causa).
Sirve de guardia contra escrituras ajenas parciales (tuneladora/agentes)
que dejan archivos rotos en el árbol de trabajo.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def _changed_py_files() -> list[Path]:
    out = subprocess.run(
        ["git", "status", "--short"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    files = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].startswith(("M", "A", "R", "??")):
            path = ROOT / parts[-1]
            if path.suffix == ".py":
                files.append(path)
    return files


def _check(files: list[Path]) -> int:
    errors = 0
    for f in files:
        try:
            ast.parse(f.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            errors += 1
            print(f"SYNTAX-ERR: {f.relative_to(ROOT)}:{exc.lineno}: {exc.msg}")
    return errors


def main() -> int:
    if "--all" in sys.argv:
        files = sorted(ROOT.rglob("*.py"))
        files = [
            f
            for f in files
            if ".venv" not in f.parts
            and "__pycache__" not in f.parts
            and "mutants" not in f.parts
            and ".tuneladora" not in f.parts
            and ".nervioso" not in f.parts
            and "build" not in f.parts
        ]
    else:
        files = _changed_py_files()
    if not files:
        print("OK: sin archivos .py modificados")
        return 0
    errors = _check(files)
    if errors:
        print(f"FAIL: {errors} archivo(s) con SyntaxError")
        return 1
    print(f"OK: {len(files)} archivo(s) .py parsean correctamente")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

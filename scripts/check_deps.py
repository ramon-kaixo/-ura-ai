#!/usr/bin/env python3
"""check_deps.py – Static import analysis.

Parses all .py files in SOURCE_DIR, extracts every `import X` / `from X import y`,
resolves each top-level package, and reports any that fail to import.
Safer than exec()-based checking because it never runs the target code.
"""

import ast
import importlib
import os
import sys
from pathlib import Path

SOURCE_DIR = Path(os.environ.get("SOURCE_DIR", os.path.expanduser("~/URA/ura_ia_1972")))
EXCLUDE_DIRS = {"venv", "__pycache__", ".git", "node_modules", "archive", "backups"}
LOCAL_PACKAGES = {
    "core",
    "agents",
    "config",
    "scripts",
    "bin",
    "api",
    "connectors",
    "services",
    "ui",
    "dashboard",
    "gateway",
    "orquestador",
}

STDLIB_MODULES: set[str] | None = None


def _get_stdlib() -> set[str]:
    global STDLIB_MODULES
    if STDLIB_MODULES is None:
        STDLIB_MODULES = getattr(sys, "stdlib_module_names", set())
    return STDLIB_MODULES


def extract_imports(path: Path) -> set[str]:
    with open(path) as fh:
        try:
            tree = ast.parse(fh.read())
        except SyntaxError:
            return set()
    top_level: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                top_level.add(top)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                top = node.module.split(".")[0]
                top_level.add(top)
    return top_level


def main() -> int:
    stdlib = _get_stdlib()
    errors: list[tuple[str, str]] = []
    seen: set[str] = set()

    for root, dirs, files in os.walk(SOURCE_DIR):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for f in files:
            if not f.endswith(".py"):
                continue
            path = Path(root) / f
            for mod in extract_imports(path):
                if mod in seen or mod in stdlib or mod in LOCAL_PACKAGES:
                    continue
                seen.add(mod)
                try:
                    importlib.import_module(mod)
                except ImportError:
                    errors.append((str(path.relative_to(SOURCE_DIR)), mod))

    if errors:
        for filepath, mod in errors:
            print(f"  {mod}  ←  {filepath}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

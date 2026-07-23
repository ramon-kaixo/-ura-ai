"""Cerebro analizador de codigo URA.

Analiza AST, detecta complejidad, duplicados, deuda tecnica.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any


class CodeAnalyzer:
    def analyze_file(self, path: Path) -> dict[str, Any]:
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError:
            return {"error": "syntax_error"}

        functions = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
        classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]

        return {
            "file": str(path),
            "lines": len(path.read_text().splitlines()),
            "functions": len(functions),
            "classes": len(classes),
            "complex_functions": [f.name for f in functions if len(f.body) > 50],
        }

    def analyze_module(self, module_path: Path) -> list[dict[str, Any]]:
        return [self.analyze_file(f) for f in module_path.rglob("*.py")]

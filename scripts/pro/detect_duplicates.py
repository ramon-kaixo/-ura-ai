#!/usr/bin/env python3
"""Detecta codigo duplicado >20 lineas en motor/."""

import ast
from collections import defaultdict
from pathlib import Path


def get_function_bodies(root: Path):
    bodies = defaultdict(list)
    for f in root.rglob("*.py"):
        try:
            tree = ast.parse(f.read_text())
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    body = ast.dump(node.body)
                    bodies[body].append(f"{f}:{node.lineno}:{node.name}")
        except SyntaxError:
            continue
    return {k: v for k, v in bodies.items() if len(v) > 1 and len(k) > 200}


if __name__ == "__main__":
    dups = get_function_bodies(Path("motor"))
    for body, locations in dups.items():
        print(f"DUPLICATE ({len(locations)} occurrences):")
        for loc in locations:
            print(f"  {loc}")

#!/usr/bin/env python3
"""Genera reporte de deuda tecnica acumulada. Sin shell=True."""
import ast
from pathlib import Path


def count_todos():
    return sum(1 for f in Path("motor").rglob("*.py") for line in f.read_text().splitlines() if "TODO" in line)

def count_fixmes():
    return sum(1 for f in Path("motor").rglob("*.py") for line in f.read_text().splitlines() if "FIXME" in line)

def count_except_pass():
    c = 0
    for f in Path("motor").rglob("*.py"):
        try:
            tree = ast.parse(f.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Try):
                    for handler in node.handlers:
                        if handler.type is None and len(handler.body) == 1:
                            if isinstance(handler.body[0], ast.Pass):
                                c += 1
        except SyntaxError:
            continue
    return c

print("=== TECH DEBT REPORT ===")
print(f"TODO comments: {count_todos()}")
print(f"FIXME comments: {count_fixmes()}")
print(f"except: pass: {count_except_pass()}")

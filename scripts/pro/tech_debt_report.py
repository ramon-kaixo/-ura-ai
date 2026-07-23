#!/usr/bin/env python3
"""Genera reporte de deuda tecnica acumulada."""
import subprocess
from pathlib import Path

BASE = Path.home() / "URA" / "ura_ia_1972"


def run(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=str(BASE)).stdout


print("=== TECH DEBT REPORT ===")
todo = run('grep -rn "TODO" motor/ --include=*.py | wc -l').strip()
fixme = run('grep -rn "FIXME" motor/ --include=*.py | wc -l').strip()
exc = run('grep -rn "except:.*pass" motor/ --include=*.py | grep -v __pycache__ | wc -l').strip()
ruff = run('.venv/bin/ruff check motor/ --output-format=concise 2>&1 | wc -l').strip()
print(f"TODO comments: {todo}")
print(f"FIXME comments: {fixme}")
print(f"except:.*pass: {exc}")
print(f"Ruff errors: {ruff}")

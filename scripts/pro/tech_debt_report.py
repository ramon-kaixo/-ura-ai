#!/usr/bin/env python3
"""Genera reporte de deuda tecnica acumulada."""
import subprocess
import sys
from pathlib import Path

def run(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout

print("=== TECH DEBT REPORT ===")
todo_count = run('grep -rn "TODO" motor/ --include=*.py | wc -l').strip()
fixme_count = run('grep -rn "FIXME" motor/ --include=*.py | wc -l').strip()
exc_count = run('grep -rn "except:.*pass" motor/ --include=*.py | grep -v "__pycache__" | wc -l').strip()
ruff_count = run('cd /home/ramon/URA/ura_ia_1972 && .venv/bin/ruff check motor/ --output-format=concise 2>&1 | wc -l').strip()
print(f"TODO comments: {todo_count}")
print(f"FIXME comments: {fixme_count}")
print(f"except:.*pass: {exc_count}")
print(f"Ruff errors: {ruff_count}")
for line in run("grep -rn 'FIXME\|TODO' motor/ --include=*.py | head -20").split("\n"):
    if line.strip():
        print(f"  {line.strip()}")

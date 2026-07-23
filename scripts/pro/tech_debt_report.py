#!/usr/bin/env python3
"""Genera reporte de deuda tecnica acumulada."""
import subprocess
from pathlib import Path

BASE = Path.home() / "URA" / "ura_ia_1972"


def _run(*args: str) -> str:
    return subprocess.run(
        list(args), capture_output=True, text=True, cwd=str(BASE)
    ).stdout


print("=== TECH DEBT REPORT ===")
todo = _run("grep", "-rn", "TODO", "motor/", "--include=*.py").count("\n")
fixme = _run("grep", "-rn", "FIXME", "motor/", "--include=*.py").count("\n")
exc = _run("grep", "-rn", "except:", "motor/", "--include=*.py").count("\n")
ruff = _run(str(BASE / ".venv" / "bin" / "ruff"), "check", "motor/", "--output-format=concise").count("motor/")
print(f"TODO comments: {todo}")
print(f"FIXME comments: {fixme}")
print(f"except: lines: {exc}")
print(f"Ruff errors: {ruff}")

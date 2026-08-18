#!/usr/bin/env python3
"""Orquestador de health checks — ejecuta antes de push."""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def main() -> int:
    # Usa make validate (filtra @slow, ejecuta pre-commit, etc.)
    r = subprocess.run(  # noqa: PLW1510 — legacy/estable, sin cambio de comportamiento
        ["make", "validate"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    print(r.stdout)
    if r.stderr:
        print(r.stderr, file=sys.stderr)
    if r.returncode != 0:
        print("❌ make validate falló. NO hagas push.", file=sys.stderr)
        return 1
    print("✅ make validate pasa. Puedes push.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

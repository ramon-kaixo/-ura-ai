#!/usr/bin/env python3
"""Orquestador de health checks — ejecuta antes de push."""
import subprocess, sys


def main() -> int:
    # Suite rápida: unit + integration
    r = subprocess.run(
        ["python3", "-m", "pytest", "tests/unit/", "tests/integration/", "-q", "--timeout=60"],
        capture_output=True, text=True,
    )
    print(r.stdout)
    if r.returncode != 0:
        print("❌ Suite falla. NO hagas push.", file=sys.stderr)
        return 1
    print("✅ Suite pasa. Puedes push.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

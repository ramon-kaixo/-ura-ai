#!/usr/bin/env python3
"""Gate obligatorio entre fases del pipeline QA."""

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
VENV_PY = REPO / ".venv/bin/python"
VENV_RUFF = REPO / ".venv/bin/ruff"
VENV_MYPY = REPO / ".venv/bin/mypy"


def run(cmd_list, timeout=300):
    try:
        r = subprocess.run(cmd_list, cwd=REPO, capture_output=True, text=True, timeout=timeout, check=False)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except Exception as e:
        return 127, "", str(e)


def git_dirty():
    r = subprocess.run(
        ["git", "-C", str(REPO), "status", "--short"],
        capture_output=True,
        text=True,
        check=False,
    )
    return [l.strip() for l in r.stdout.splitlines() if l.strip()]


def registrar(fase, ok, detalles):
    coord = REPO / "docs/udo/coordination.json"
    try:
        data = json.loads(coord.read_text(encoding="utf-8"))
        data.setdefault("phase_gates", {})
        data["phase_gates"][fase] = {
            "ok": ok,
            "fecha": datetime.now(UTC).isoformat(),
            "detalles": detalles[:400],
        }
        coord.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"WARN: no se pudo actualizar coordination.json: {e}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fase", required=True)
    parser.add_argument("--archivo", default="")
    parser.add_argument("--check-dirty", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    acciones = []
    errores = []

    dirty = git_dirty()
    if args.check_dirty and dirty:
        errores.append(f"git dirty: {dirty[:5]}")
    elif dirty:
        print(f"WARN: {len(dirty)} archivos dirty")

    # Ruff
    if args.archivo:
        acciones.append([str(VENV_RUFF), "check", args.archivo])
    else:
        acciones.append([str(VENV_RUFF), "check", "scripts/pro/qa_common.py"])

    # Mypy
    if args.archivo:
        acciones.append([str(VENV_MYPY), "--no-incremental", args.archivo])
    else:
        acciones.append([str(VENV_MYPY), "--no-incremental", "scripts/pro/qa_common.py"])

    # Pytest de protocolo
    acciones.append([str(VENV_PY), "-m", "pytest", "tests/unit/test_protocol_coordination.py", "-q", "--tb=short"])

    if args.dry_run:
        print("DRY RUN — comprobaciones:")
        for a in acciones:
            print("  " + " ".join(a))
        return 0

    for cmd in acciones:
        code, _out, err = run(cmd)
        if code != 0:
            errores.append(f"{' '.join(cmd)} => code={code}\n{err[-500:]}")

    ok = not errores
    registrar(args.fase, ok, "; ".join(errores) if errores else "OK")

    if not ok:
        print(f"PHASE_GATE FAIL fase={args.fase}")
        for e in errores:
            print("---")
            print(e)
        sys.exit(1)

    print(f"PHASE_GATE OK fase={args.fase}")
    sys.exit(0)


if __name__ == "__main__":
    main()

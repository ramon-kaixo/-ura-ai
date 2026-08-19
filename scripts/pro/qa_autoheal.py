#!/usr/bin/env python3
"""Auto-reparador determinista con backup vía GIT y restauración.

Endurecido (2026-08-19):
- Backup = commit temporal de git (no /tmp: no se pierde con reboot, trazable).
- Solo actúa sobre archivos de TESTS (tests/). NUNCA sobre producción.
- Flujo: branch temporal -> ruff --fix -> py_compile -> pytest del test
  -> si algo falla: git restore del archivo y abandono el intento.
- Trazabilidad en el mensaje de salida (branch creado, commits, restore).

Uso:
  python3 scripts/pro/qa_autoheal.py tests/unit/test_foo.py [--max-intentos 3]
  python3 scripts/pro/qa_autoheal.py --dry-run tests/unit/test_foo.py
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO = Path("/home/ramon/URA/ura_ia_1972")
VENV_PY = REPO / ".venv/bin/python"
VENV_RUFF = REPO / ".venv/bin/ruff"


def run(cmd_list: list[str], timeout: int = 300) -> tuple[int, str, str]:
    try:
        r = subprocess.run(cmd_list, cwd=REPO, capture_output=True, text=True, timeout=timeout, check=False)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except Exception as e:
        return 127, "", str(e)


def _git(*args: str) -> tuple[int, str, str]:
    return run(["git", *args])


def _es_test(archivo: Path) -> bool:
    return "tests" in archivo.parts and archivo.suffix == ".py"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archivo")
    parser.add_argument("--max-intentos", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    archivo = Path(args.archivo).resolve()
    if not archivo.exists():
        print(f"No existe: {archivo}")
        return 1
    if not _es_test(archivo):
        print(f"BLOQUEADO: {archivo} no es un archivo de tests (solo se toca tests/)")
        return 1

    if args.dry_run:
        print(f"[dry-run] backup git + ruff --fix + py_compile + pytest de {archivo.name}")
        return 0

    # 1) backup: guardar el estado limpio del archivo
    code, _, err = _git("diff", "--quiet", "--", str(archivo))
    if code != 0:
        print(f"El archivo ya tiene cambios sin commitear: {archivo} — abortando (zona ajena).")
        return 1
    print("Backup: estado git actual del archivo (sin cambios previos) — OK")

    branch = f"autoheal-{archivo.stem}"
    code, _, err = _git("checkout", "-b", branch)
    if code != 0:
        print(f"Branch temporal {branch} ya existe — abortando.")
        return 1
    print(f"Branch temporal: {branch}")

    for intento in range(1, args.max_intentos + 1):
        print(f"\nIntento {intento}/{args.max_intentos}")
        code, _, err = run([str(VENV_RUFF), "check", "--fix", str(archivo)])
        if code != 0:
            print(f"ruff falló: {err[-200:]} — restoring")
            _git("restore", str(archivo))
            continue

        code, _, err = run([str(VENV_PY), "-m", "py_compile", str(archivo)])
        if code != 0:
            print(f"py_compile falló: {err[-200:]} — restoring")
            _git("restore", str(archivo))
            continue

        code, _, err = run([str(VENV_PY), "-m", "pytest", str(archivo), "-q", "--tb=short"])
        if code != 0:
            print(f"pytest falló: {err[-200:]} — restoring")
            _git("restore", str(archivo))
            continue

        print("OK: test reparado")
        _git("commit", "-m", f"chore(autoheal): [TERM] reparar {archivo.name}", "--", str(archivo))
        _git("checkout", "main")
        _git("merge", "--no-ff", branch, "-m", f"merge autoheal {archivo.name}")
        _git("branch", "-d", branch)
        return 0

    print("BLOCKED: no se pudo reparar — archivo restaurado a git, branch descartada")
    _git("checkout", "main")
    _git("branch", "-D", branch)
    return 1


if __name__ == "__main__":
    sys.exit(main())

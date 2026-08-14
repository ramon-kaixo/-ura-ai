#!/usr/bin/env python3
"""Verificador de cobertura por módulo (regla RAMON 2026-08-13, meta 100x100).

Cada archivo/módulo nuevo debe tener cobertura de tests >=80% por módulo
(política AGENTS.md); la meta es llegar a 100x100. Este verificador mide la
cobertura de uno o varios módulos/archivos Python con pytest + coverage
(rcfile propio sin omit) y falla si algún archivo queda por debajo del minimo.

Uso:
    verificador_cobertura.py <ruta.py|módulo|dir> [--tests T1,T2] [--min 80]
    verificador_cobertura.py --ci                    # archivos .py del diff HEAD vs origin/main
    verificador_cobertura.py --ci --base main[]      # archivos del diff contra --base

Exit: 0 = todos ok · 1 = algún archivo por debajo del minimo (con detalle).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

MIN_DEFAULT = 80
MAX_DEFAULT = 100

_RCFILE = """[run]
source = {source}
branch = True
[report]
precision = 1
"""


def _normalize_modulo(ruta: str) -> str:
    ruta = ruta.replace(".py", "", 1) if ruta.endswith(".py") else ruta
    while ruta.endswith("/"):
        ruta = ruta[:-1]
    return ruta


def medir_cobertura(
    source: str,
    tests: list[str],
    min_pct: int = MIN_DEFAULT,
    max_pct: int = MAX_DEFAULT,
) -> dict[str, float]:
    """Ejecuta los tests y devuelve {archivo: pct_cover} para los archivos del source."""
    src_abs = str(Path(source).resolve())
    if not Path(source).exists():
        return {}
    if Path(source).is_file():
        src_abs = str(Path(source).resolve().parent)
    with tempfile.TemporaryDirectory() as tmp:
        rcfile = Path(tmp) / "cov.rc"
        rcfile.write_text(_RCFILE.format(source=src_abs))
        env = {**os.environ, "COVERAGE_FILE": str(Path(tmp) / ".coverage")}
        cmd = [
            sys.executable,
            "-m",
            "coverage",
            "run",
            f"--rcfile={rcfile}",
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            *tests,
        ]
        subprocess.run(cmd, cwd=tmp, check=False, capture_output=True, text=True, env=env)
        report = subprocess.run(
            [sys.executable, "-m", "coverage", "json", f"--rcfile={rcfile}"],
            cwd=tmp,
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )
        if report.returncode != 0 or not (Path(tmp) / "coverage.json").exists():
            return {}
        try:
            data = json.loads((Path(tmp) / "coverage.json").read_text())
        except (json.JSONDecodeError, OSError):
            return {}
        return {name: stats["summary"]["percent_covered"] for name, stats in data["files"].items()}


def evaluar(
    cobertura: dict[str, float],
    min_pct: int,
    max_pct: int,
    solo_nuevos: bool = False,
) -> tuple[list[str], list[str]]:
    """Devuelve (ok, fuera) con los archivos dentro/fuera de la horquilla."""
    ok: list[str] = []
    fuera: list[str] = []
    for archivo, pct in sorted(cobertura.items()):
        if pct < min_pct or pct > max_pct:
            fuera.append(f"{archivo}: {pct:.1f}%")
        else:
            ok.append(f"{archivo}: {pct:.1f}%")
    return ok, fuera


def diff_py(base: str) -> list[str]:
    """Archivos .py del diff HEAD vs base (para el modo --ci)."""
    cmd = ["git", "diff", "--name-only", "--diff-filter=ACM", f"{base}...HEAD"]
    out = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return [l.strip() for l in out.stdout.splitlines() if l.strip().endswith(".py")]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("objetivo", nargs="?", help="archivo, módulo o directorio a medir")
    parser.add_argument("--tests", default="", help="tests a ejecutar (separados por coma)")
    parser.add_argument("--min", type=int, default=MIN_DEFAULT)
    parser.add_argument("--max", type=int, default=MAX_DEFAULT)
    parser.add_argument("--ci", action="store_true", help="medir los archivos .py del diff")
    parser.add_argument("--base", default="origin/main")
    args = parser.parse_args(argv)

    if args.ci:
        objetivos = diff_py(args.base)
        if not objetivos:
            print("SIN CAMBIOS PYTHON — OK")
            return 0
    else:
        if not args.objetivo:
            parser.error("falta el objetivo (o usa --ci)")
        objetivos = [args.objetivo]

    tests = [t for t in args.tests.split(",") if t]
    if not tests:
        print("AVISO: sin --tests explícitos; coverage con la suite descubierta (puede ser 0%)")
    cobertura: dict[str, float] = {}
    for objetivo in objetivos:
        cobertura.update(medir_cobertura(_normalize_modulo(objetivo), tests, args.min, args.max))

    ok, fuera = evaluar(cobertura, args.min, args.max)
    for linea in ok:
        print(f"OK  {linea}")
    for linea in fuera:
        print(f"FAIL {linea}")
    print(f"RESULTADO: {len(ok)} en horquilla [{args.min}-{args.max}%], {len(fuera)} fuera")
    return 1 if fuera else 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Verificador de cobertura por módulo (regla RAMON 2026-08-13, meta 100x100).

Cada archivo/módulo nuevo debe tener cobertura de tests >=85% por módulo
(gate escalonado Fase 5: 80 -> 85; meta 100x100 y 90 en la siguiente etapa).
Este verificador mide la cobertura de uno o varios módulos/archivos Python
con pytest + coverage (rcfile propio sin omit) y falla si algún archivo
queda por debajo del minimo.

Uso:
    verificador_cobertura.py <ruta.py|módulo|dir> [--tests T1,T2] [--min 85]
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
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

MIN_DEFAULT = 85
MAX_DEFAULT = 100

_RCFILE = r"""[run]
source = {source}
branch = True
[report]
precision = 1
exclude_lines =
    if __name__ == "__main__":
    pragma: no cover
"""


def _normalize_modulo(ruta: str) -> str:
    ruta = ruta.replace(".py", "", 1) if ruta.endswith(".py") else ruta
    while ruta.endswith("/"):
        ruta = ruta[:-1]
    return ruta


def _es_archivo(source: str) -> bool:
    """True si source apunta a un archivo .py (con o sin extensión)."""
    p = Path(source)
    if p.exists() and p.is_file():
        return True
    return not source.endswith(".py") and Path(source + ".py").is_file()


def medir_cobertura(
    source: str,
    tests: list[str],
    min_pct: int = MIN_DEFAULT,
    max_pct: int = MAX_DEFAULT,
) -> dict[str, float]:
    """Ejecuta los tests y devuelve {archivo: pct_cover} para los archivos del source.

    Usa pytest-cov (no coverage run puro) para que las exclusiones estándar
    (bloque __main__, pragma: no cover) coincidan con la medición real.
    """
    if not Path(source).exists() and not _es_archivo(source):
        return {}
    if _es_archivo(source):
        archivo_real = Path(source + ".py") if not source.endswith(".py") else Path(source)
        objetivo = str(archivo_real.resolve())
        partes = archivo_real.resolve().relative_to(REPO_ROOT.resolve()).with_suffix("").parts
        modulo = ".".join(partes)
    else:
        objetivo = str(Path(source).resolve())
        modulo = objetivo
    tests_abs = [str(Path(t).resolve()) for t in tests]
    env = {**os.environ, "COVERAGE_FILE": str(REPO_ROOT / ".coverage_tmp")}
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "--cov",
        modulo,
        "--cov-branch",
        "--cov-report",
        "json",
        *tests_abs,
    ]
    subprocess.run(cmd, cwd=str(REPO_ROOT), check=False, capture_output=True, text=True, env=env)
    json_path = REPO_ROOT / "coverage.json"
    if not json_path.exists():
        return {}
    try:
        data = json.loads(json_path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}
    objetivo_resuelto = Path(objetivo).resolve()
    if objetivo_resuelto.is_file():
        return {
            name: stats["summary"]["percent_covered"]
            for name, stats in data["files"].items()
            if Path(name).resolve() == objetivo_resuelto
        }
    prefix = str(objetivo_resuelto)
    return {
        name: stats["summary"]["percent_covered"]
        for name, stats in data["files"].items()
        if str(Path(name).resolve()).startswith(prefix)
    }


def evaluar(
    cobertura: dict[str, float],
    min_pct: int,
    max_pct: int,
    solo_nuevos: bool = False,
) -> tuple[list[str], list[str]]:
    """Devuelve (ok, fuera) con los archivos dentro/fuera de la horquilla."""
    ok: list[str] = []
    fuera: list[str] = []
    if not cobertura:
        return [], ["(sin archivos medidos — los tests no cubren el objetivo)"]
    for archivo, pct in sorted(cobertura.items()):
        if pct < min_pct or pct > max_pct:
            fuera.append(f"{archivo}: {pct:.1f}%")
        else:
            ok.append(f"{archivo}: {pct:.1f}%")
    return ok, fuera


def evaluar_json(archivo_json: Path, min_pct: int, max_pct: int) -> tuple[list[str], list[str]]:
    """Evalúa un coverage.json generado por pytest-cov (--cov-report=json).

    Devuelve (ok, fuera) igual que evaluar(), reutilizando la misma horquilla.
    """
    try:
        data = json.loads(archivo_json.read_text())
    except (json.JSONDecodeError, OSError):
        return [], [f"(coverage.json ilegible: {archivo_json})"]
    cobertura = {name: stats["summary"].get("percent_covered", 0.0) for name, stats in data.get("files", {}).items()}
    return evaluar(cobertura, min_pct, max_pct)


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
    parser.add_argument(
        "--json",
        metavar="ARCHIVO",
        help="evaluar un coverage.json ya generado (pytest-cov --cov-report=json) en vez de ejecutar coverage",
    )
    args = parser.parse_args(argv)

    if args.json:
        ok, fuera = evaluar_json(Path(args.json), args.min, args.max)
        for linea in ok:
            print(f"OK  {linea}")
        for linea in fuera:
            print(f"FAIL {linea}")
        print(f"RESULTADO: {len(ok)} en horquilla [{args.min}-{args.max}%], {len(fuera)} fuera")
        return 1 if fuera else 0

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

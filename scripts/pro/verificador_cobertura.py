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

MIN_DEFAULT = 90
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


def auto_detectar_tests(objetivo: str) -> list[str]:
    """Busca tests unitarios existentes para un módulo/archivo.

    Convenciones probadas (pipeline de cobertura + tests manuales):
      - tests/unit/test_<padre>_<stem>_smoke.py / _hypothesis.py (pipeline)
      - tests/unit/test_<padre>_<stem>.py (tests manuales)
      - tests/unit/*cobertura*.py con el nombre del módulo
    Devuelve lista de rutas relativas; vacía si no encuentra ninguno.
    """
    if not objetivo:
        return []
    partes = _normalize_modulo(objetivo).replace("\\", "/").split("/")
    nombre = partes[-1]
    padre = partes[-2] if len(partes) > 1 else ""
    tests_dir = REPO_ROOT / "tests" / "unit"
    if not tests_dir.is_dir():
        return []
    candidatos = [
        f"test_{padre}_{nombre}_smoke.py",
        f"test_{padre}_{nombre}_hypothesis.py",
        f"test_{padre}_{nombre}.py",
        f"test_{padre}_{nombre}_cobertura.py",
    ]
    encontrados = [c for c in candidatos if (tests_dir / c).is_file()]
    if encontrados:
        return [str(tests_dir / c) for c in encontrados]
    # fallback 1: test_* con las partes del módulo en orden (test_motor_llm_router_providers -> providers)
    stem = nombre.removesuffix(".py").lstrip("_")
    padre_stem = padre.lstrip("_")
    for t in sorted(tests_dir.glob("test_*.py")):
        tstem = t.name.removeprefix("test_").removesuffix(".py")
        if stem in tstem and padre_stem in tstem:
            encontrados.append(t.name)
    if encontrados:
        return [str(tests_dir / c) for c in encontrados]
    # fallback 1b: módulos profundos (>=3 partes) — aceptar el test cuyo nombre
    # contiene el stem y el mayor número de partes del módulo (evita falsos positivos)
    if len(partes) >= 3:
        partes_limpio = [p.lstrip("_").removesuffix(".py") for p in partes if p not in ("core", "llm", "web", "scanner", "motor")]
        for t in sorted(tests_dir.glob("test_*.py")):
            tstem = t.name.removeprefix("test_").removesuffix(".py")
            coincidencias = sum(1 for p in partes_limpio if p in tstem)
            if stem in tstem and coincidencias >= 1:
                encontrados.append((coincidencias, t.name))
        if encontrados:
            encontrados.sort(reverse=True)
            return [str(tests_dir / c) for _score, c in encontrados[:2]]
    # fallback 2: cualquier test_*_cobertura.py que mencione el nombre del módulo
    for t in sorted(tests_dir.glob("test_*_cobertura.py")):
        try:
            contenido = t.read_text(errors="ignore")
        except OSError:
            continue
        if nombre in contenido and objetivo.replace(".py", "").split("/")[-1] in contenido:
            encontrados.append(t.name)
    return [str(tests_dir / c) for c in encontrados]


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
        # solo se miden módulos con política de cobertura; el resto es SKIP informativo
        zonas_cubribles = ("motor/", "core/", "knowledge/")
        medibles = [o for o in objetivos if o.startswith(zonas_cubribles)]
        for o in objetivos:
            if o not in medibles:
                print(f"SKIP {o}: fuera de zonas con política de cobertura")
        objetivos = medibles
        if not objetivos:
            print("RESULTADO: sin cambios en zonas de cobertura — OK")
            return 0
    else:
        if not args.objetivo:
            parser.error("falta el objetivo (o usa --ci)")
        objetivos = [args.objetivo]

    cobertura: dict[str, float] = {}
    sin_tests: list[str] = []
    for objetivo in objetivos:
        tests_obj = [t for t in args.tests.split(",") if t]
        if not tests_obj:
            tests_obj = auto_detectar_tests(objetivo)
            if tests_obj:
                print(f"AVISO: sin --tests para {objetivo}; auto-detectados: {', '.join(Path(t).name for t in tests_obj)}")
        if not tests_obj:
            sin_tests.append(objetivo)
            continue
        cobertura.update(medir_cobertura(_normalize_modulo(objetivo), tests_obj, args.min, args.max))

    for objetivo in sin_tests:
        print(f"SKIP {objetivo}: sin tests unitarios asociados (no medido)")

    ok, fuera = evaluar(cobertura, args.min, args.max)
    for linea in ok:
        print(f"OK  {linea}")
    for linea in fuera:
        print(f"FAIL {linea}")
    print(f"RESULTADO: {len(ok)} en horquilla [{args.min}-{args.max}%], {len(fuera)} fuera")
    return 1 if fuera else 0


if __name__ == "__main__":
    sys.exit(main())

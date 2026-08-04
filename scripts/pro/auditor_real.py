"""auditor_real.py — Auditoría real de TODO el repo (Fase 1 adaptada).

Para cada archivo .py registra:
  - líneas, main/class/PLUGIN, tests asociados, imports reales, última modificación
  - estado propuesto: activo / dormido / obsoleto / demo / rpa / esbozo / corrupto / libreria

Fuentes de verdad: git history (NO build/), imports reales, tests reales.
Salida: docs/auditoria_real.json | .md | .csv
Uso: python3 scripts/pro/auditor_real.py
"""
from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_DIR = REPO_ROOT / "docs"
EXCLUDE_DIRS = {
    "build", ".sandbox_packages", ".venv", ".git", ".attic", ".nervioso",
    "__pycache__", ".tuneladora", "data", "logs", "models", "backups", "backup_versiones",
    "apple-ncm", "dist", "ura.egg-info", "htmlcov", "requirements",
}
TESTS_DIRS = [REPO_ROOT / "tests" / "unit", REPO_ROOT / "tests" / "integration"]

MAKEFILE = REPO_ROOT / "Makefile"

DEFAULT_JSON = OUT_DIR / "auditoria_real.json"
DEFAULT_MD = OUT_DIR / "auditoria_real.md"
DEFAULT_CSV = OUT_DIR / "auditoria_real.csv"


def _walk() -> list[Path]:
    return [
        p
        for p in sorted(REPO_ROOT.rglob("*.py"))
        if p.is_file() and not any(part in EXCLUDE_DIRS for part in p.relative_to(REPO_ROOT).parts)
    ]


def _git_mtime_map() -> dict[str, str]:
    try:
        raw = subprocess.run(
            ["git", "log", "--format=%ci|", "--name-only"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=180,
        ).stdout
    except (subprocess.TimeoutExpired, OSError):
        return {}
    result: dict[str, str] = {}
    date = ""
    for line in raw.splitlines():
        if line.endswith("|"):
            date = line.strip("| ")
        elif line and date:
            result.setdefault(line, date)
    return result


def _has_tests(stem: str) -> bool:
    return any((d / f"test_{stem}.py").exists() for d in TESTS_DIRS)


def _classify(rel: str, name: str, lines: int, has_main: bool, has_class: bool, is_imported: bool, has_tests: bool, corrupto: bool) -> str:
    if corrupto:
        return "corrupto"
    if "demo_" in name:
        return "demo"
    if name.startswith(("rpa_", "bypass_")):
        return "rpa"
    if "patch_" in name or "seed_" in name:
        return "obsoleto"
    if name == "__init__.py" or name == "__main__.py":
        return "libreria"
    if rel.startswith("tests/") or rel.startswith("motor/tests/"):
        return "test"
    if lines < 20 and not has_class:
        return "esbozo"
    if not has_main and not has_class:
        return "libreria"
    if has_tests or is_imported:
        return "activo"
    return "dormido"


def _referenciado_por_sistema() -> set[str]:
    """Rutas de scripts referenciados por systemd, cron o el Makefile."""
    refs: set[str] = set()
    import subprocess as sp

    try:
        units = sp.run(["systemctl", "list-unit-files"], capture_output=True, text=True, timeout=30).stdout
        for stem in re.findall(r"(\S+)\.(?:service|timer|path)", units):
            refs.add(stem)
    except (OSError, sp.TimeoutExpired):
        pass
    try:
        cron = sp.run(["crontab", "-l"], capture_output=True, text=True, timeout=30).stdout
        for stem in re.findall(r"(\S+)\.(?:py|sh)", cron):
            refs.add(Path(stem).stem)
    except (OSError, sp.TimeoutExpired):
        pass
    if MAKEFILE.exists():
        for stem in re.findall(r"(?:scripts/pro/|scripts/)?(\w+\.(?:py|sh))", MAKEFILE.read_text()):
            refs.add(Path(stem).stem)
    return refs


def main() -> int:
    t0 = time.monotonic()
    paths = _walk()
    print(f"[1/4] walk: {len(paths)} archivos .py ({time.monotonic() - t0:.0f}s)", flush=True)

    t0 = time.monotonic()
    mtime_map = _git_mtime_map()
    print(f"[2/4] git log: {len(mtime_map)} rutas con fecha ({time.monotonic() - t0:.0f}s)", flush=True)

    t0 = time.monotonic()
    fuentes: dict[str, str] = {}
    for p in paths:
        try:
            fuentes[str(p.relative_to(REPO_ROOT))] = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            fuentes[str(p.relative_to(REPO_ROOT))] = ""
    print(f"[3/4] lectura: {len(fuentes)} archivos ({time.monotonic() - t0:.0f}s)", flush=True)

    corpus = "\n".join(fuentes.values())

    import re

    referenced = set(re.findall(r"(?:import|from)\s+([a-zA-Z0-9_]+)", corpus))
    referenced_py = set(re.findall(r"([a-zA-Z0-9_]+)\.py", corpus))
    sistema_refs = _referenciado_por_sistema()

    entries: list[dict] = []
    for rel, src in fuentes.items():
        lines = src.count("\n") + 1
        has_main = '__name__ == "__main__"' in src
        has_class = "class " in src
        has_plugin = "PLUGIN" in src
        stem = Path(rel).stem
        try:
            compile(src, rel, "exec")
            corrupto = False
        except (SyntaxError, UnicodeDecodeError, ValueError):
            corrupto = True
        is_imported = stem in referenced or stem in referenced_py or stem in sistema_refs
        has_tests = _has_tests(stem)
        estado = _classify(rel, stem, lines, has_main, has_class, is_imported, has_tests, corrupto)
        entries.append(
            {
                "ruta": rel,
                "lineas": lines,
                "main": has_main,
                "class": has_class,
                "plugin": has_plugin,
                "tests": has_tests,
                "importado": is_imported,
                "ultima_mod": mtime_map.get(rel, ""),
                "estado": estado,
            },
        )

    OUT_DIR.mkdir(exist_ok=True)
    now = datetime.now(UTC).isoformat()
    DEFAULT_JSON.write_text(json.dumps({"generado": now, "total": len(entries), "archivos": entries}, indent=2))

    with DEFAULT_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(entries[0].keys()))
        writer.writeheader()
        writer.writerows(entries)

    por_estado: dict[str, int] = {}
    for e in entries:
        por_estado[e["estado"]] = por_estado.get(e["estado"], 0) + 1

    md = [f"# Auditoría Real — {now}", "", f"Total archivos: {len(entries)}", "", "## Resumen por estado", ""]
    md.append("| Estado | Cantidad |")
    md.append("|---|---|")
    for estado, n in sorted(por_estado.items()):
        md.append(f"| {estado} | {n} |")
    md.append("")
    md.append("## Detalle")
    md.append("")
    md.append("| Ruta | Líneas | main | class | PLUGIN | tests | importado | última mod | estado |")
    md.append("|---|---|---|---|---|---|---|---|---|")
    for e in entries:
        md.append(
            f"| {e['ruta']} | {e['lineas']} | {e['main']} | {e['class']} | {e['plugin']} | "
            f"{e['tests']} | {e['importado']} | {e['ultima_mod'][:10]} | {e['estado']} |",
        )
    DEFAULT_MD.write_text("\n".join(md) + "\n")

    print(f"[4/4] total: {len(entries)} — {time.monotonic() - t0:.0f}s", flush=True)
    for estado, n in sorted(por_estado.items()):
        print(f"  {estado}: {n}")
    print(f"JSON: {DEFAULT_JSON}\nMD:   {DEFAULT_MD}\nCSV:  {DEFAULT_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

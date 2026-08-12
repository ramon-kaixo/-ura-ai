#!/usr/bin/env python3
"""plan_fondo.py — Planificador jerárquico del modo de revisión de fondo (v2).

Calcula la siguiente tarea de revisión para el TERM:
- Recorre el árbol del repo en orden: carpetas principales primero, luego
  sus subcarpetas (profundidad ascendente), sin repetir (lee el progreso).
- Limita cada turno a MAX_ARCHIVOS archivos con lista EXPLÍCITA, para que
  el TERM lea el código completo y no especule (reduce falsos positivos).
- Soportes lotes: si una carpeta tiene más archivos que el límite, se
  divide en lotes (carpeta (lote k/N)) registrados en el progreso.

Uso: python3 plan_fondo.py <repo> <hallazgos_md>
Salida (stdout, JSON): {"carpeta": "...", "archivos": [...], "lote": k,
  "total_lotes": N, "tipo": "lote"|"carpeta", "completa": bool}
  o {"carpeta": "", "error": "mapa agotado"} si todo está revisado.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

MAX_ARCHIVOS = 30
EXCLUIR_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", ".tuneladora", ".nervioso",
    ".opencode", "snapshots", "dist", "build", ".pytest_cache", ".ruff_cache",
    "mutation-reports", "descarte", "backup", ".sandbox_packages", "build",
    "site-packages", ".cache", ".local",
}
# Raíces principales: se recorren primero (profundidad 1), en este orden.
RAICES_PRINCIPALES = [
    "core", "motor", "agents", "knowledge", "scripts/pro", "monitor",
    "deploy", "tests", "docs", "mantenimiento",
]
EXT_FUENTE = {".py", ".sh", ".js", ".ts", ".json", ".yaml", ".yml", ".toml", ".md"}


def _es_fuente(p: Path) -> bool:
    return p.suffix in EXT_FUENTE and "test" not in p.name.lower()


def _carpetas_plan(repo: Path, max_depth: int = 4) -> list[dict]:
    """Devuelve las carpetas con sus archivos fuente, ordenadas por (profundidad, nº archivos)."""
    plan: list[dict] = []
    for d in repo.rglob("*"):
        if not d.is_dir() or any(part in EXCLUIR_DIRS for part in d.parts):
            continue
        rel = d.relative_to(repo)
        depth = len(rel.parts)
        if depth > max_depth:
            continue
        archivos = sorted(
            (p for p in d.iterdir() if p.is_file() and _es_fuente(p)),
            key=lambda p: p.name,
        )
        if not archivos:
            continue
        plan.append({
            "carpeta": str(rel),
            "depth": depth,
            "archivos": [str(p.relative_to(repo)) for p in archivos],
            "n": len(archivos),
        })
    plan.sort(key=lambda x: (x["depth"], x["n"], x["carpeta"]))
    # Raíces principales primero (aunque tengan muchos archivos, se dividen en lotes)
    plan.sort(key=lambda x: (
        RAICES_PRINCIPALES.index(x["carpeta"]) if x["carpeta"] in RAICES_PRINCIPALES else 99,
        x["depth"], x["n"], x["carpeta"],
    ))
    return plan


def _revisadas(archivo: Path) -> set[str]:
    """Lee la sección Progreso y devuelve las carpetas/lotes ya registrados."""
    if not archivo.exists():
        return set()
    texto = archivo.read_text(errors="ignore")
    # Líneas de la tabla de Progreso: | fecha | carpeta | ...
    en_progreso = False
    revisadas: set[str] = set()
    for linea in texto.splitlines():
        if linea.strip().startswith("## Progreso"):
            en_progreso = True
            continue
        if en_progreso and linea.strip().startswith("## "):
            break
        if en_progreso and linea.strip().startswith("|"):
            partes = [p.strip() for p in linea.strip("|").split("|")]
            if len(partes) >= 2 and re.match(r"\d{4}-\d{2}-\d{2}", partes[0]):
                revisadas.add(partes[1])
    return revisadas


def _normalizar(carpeta: str) -> str:
    """'motor/intelligence/' → 'motor/intelligence'."""
    return carpeta.strip().strip("/")


def main() -> int:
    if len(sys.argv) < 3:
        print(json.dumps({"carpeta": "", "error": "uso: plan_fondo.py <repo> <hallazgos_md>"}))
        return 1
    repo = Path(sys.argv[1])
    hallazgos = Path(sys.argv[2])
    revisadas = {_normalizar(c) for c in _revisadas(hallazgos)}

    plan = _carpetas_plan(repo)
    for entry in plan:
        carpeta = entry["carpeta"]
        if carpeta in revisadas:
            continue
        # ¿Carpeta ya en curso con lotes? (carpeta (lote k/N))
        lotes_existentes = {
            c for c in revisadas
            if c.startswith(carpeta + " (lote ") or c == carpeta + " (lote completo)"
        }
        if lotes_existentes:
            continue  # carpeta ya empezada con lotes → la gestionan los lotes
        archivos = entry["archivos"]
        n = len(archivos)
        if n <= MAX_ARCHIVOS:
            # Lote completo único
            lote_actual = f"{carpeta} (lote 1/1)"
            salida = {
                "carpeta": carpeta,
                "archivos": archivos,
                "lote": 1,
                "total_lotes": 1,
                "tipo": "carpeta",
                "completa": True,
                "marcar_como": f"{carpeta} (lote completo)",
            }
            print(json.dumps(salida))
            return 0
        # Carpeta grande → primer lote
        primer = archivos[:MAX_ARCHIVOS]
        total_lotes = (n + MAX_ARCHIVOS - 1) // MAX_ARCHIVOS
        salida = {
            "carpeta": carpeta,
            "archivos": primer,
            "lote": 1,
            "total_lotes": total_lotes,
            "tipo": "lote",
            "completa": False,
            "marcar_como": f"{carpeta} (lote 1/{total_lotes})",
        }
        print(json.dumps(salida))
        return 0

    # Todo revisado → buscar lotes pendientes de carpetas grandes ya iniciadas
    for entry in plan:
        carpeta = entry["carpeta"]
        if carpeta not in revisadas:
            continue
        n = len(entry["archivos"])
        if n <= MAX_ARCHIVOS:
            continue
        total_lotes = (n + MAX_ARCHIVOS - 1) // MAX_ARCHIVOS
        for k in range(1, total_lotes + 1):
            marca = f"{carpeta} (lote {k}/{total_lotes})"
            if marca not in revisadas:
                archivos = entry["archivos"][(k - 1) * MAX_ARCHIVOS : k * MAX_ARCHIVOS]
                salida = {
                    "carpeta": carpeta,
                    "archivos": archivos,
                    "lote": k,
                    "total_lotes": total_lotes,
                    "tipo": "lote",
                    "completa": k == total_lotes,
                    "marcar_como": marca,
                }
                print(json.dumps(salida))
                return 0

    print(json.dumps({"carpeta": "", "error": "mapa agotado (todo revisado)"}))
    return 0


if __name__ == "__main__":
    sys.exit(main())

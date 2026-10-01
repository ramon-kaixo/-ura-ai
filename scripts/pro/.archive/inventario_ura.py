#!/usr/bin/env python3
"""inventario_ura.py — Inventario/árbol del sistema URA (TASK-20260812-016).

Genera el mapa completo del proyecto: para cada carpeta principal registra:
  - nombre y ruta
  - fecha de creación (git log del directorio) y última modificación
  - propósito (docstring de __init__.py o README, o heurística)
  - conexiones: qué módulos de otras carpetas importa (imports) y quién lo importa
  - nº de archivos fuente

Uso: python3 inventario_ura.py [--json] [--detalle]
Salida: tabla markdown (o JSON) + docs/architecture/INVENTARIO_URA.md
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
RAICES = [
    "core",
    "motor",
    "agents",
    "knowledge",
    "monitor",
    "scripts/pro",
    "deploy",
    "tests",
    "docs",
    "mantenimiento",
]
EXCLUIR = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    ".tuneladora",
    ".nervioso",
    "snapshots",
    "site-packages",
    "mutation-reports",
    ".attic",
    "bitacora",
    "shared",
    "specs",
    "config",
    "data",
}


def _git(cmd: list[str]) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15, cwd=REPO)  # noqa: PLW1510 — legacy/estable, sin cambio de comportamiento
        return r.stdout.strip()
    except Exception:
        return ""


def _fecha_creacion(ruta: Path) -> str:
    """Fecha del primer commit que tocó el directorio."""
    out = _git(
        [
            "git",
            "log",
            "--diff-filter=A",
            "--follow",
            "--format=%ad",
            "--date=format:%Y-%m-%d",
            "--",
            str(ruta.relative_to(REPO)),
        ]
    )
    if out:
        return out.splitlines()[-1] if out.splitlines() else ""
    out = _git(["git", "log", "--format=%ad", "--date=format:%Y-%m-%d", "--", str(ruta.relative_to(REPO))])
    return out.splitlines()[-1] if out else ""


def _fecha_mod(ruta: Path) -> str:
    out = _git(["git", "log", "-1", "--format=%ad", "--date=format:%Y-%m-%d", "--", str(ruta.relative_to(REPO))])
    return out or ""


def _proposito(ruta: Path) -> str:
    """Intenta extraer propósito del docstring del __init__.py o README del MISMO dir."""
    for cand in (ruta / "__init__.py", ruta / "README.md"):
        if cand.exists():
            texto = cand.read_text(errors="ignore")[:500]
            m = re.search(r'"""(.*?)"""', texto, re.DOTALL)
            if m:
                return " ".join(m.group(1).split())[:120]
            if cand.suffix == ".md":
                # README: usar el primer encabezado o primeras líneas de contenido
                lineas = [l.strip() for l in cand.read_text(errors="ignore").splitlines() if l.strip()]
                for l in lineas:
                    if l.startswith("#"):
                        return l.lstrip("# ")[:120]
                return " ".join(lineas[:3])[:120] if lineas else ""
            return ""
    # Heurística por nombre
    nombres = {
        "core": "Lógica de dominio (conciencia, valores, rollback, mochila)",
        "motor": "Framework motor + config única (UraConfig) + inteligencia",
        "knowledge": "Memoria a largo plazo, fragmentos, knowledge engine",
        "monitor": "SNC, supervisión, brazo de emergencia",
        "scripts/pro": "Scripts de pipeline, utilidades y automatización (~146)",
        "deploy": "Despliegue: systemd, launchd Mac, engineering",
        "tests": "Tests unitarios e integración",
        "docs": "Documentación arquitectura, ingeniería, UDO",
        "mantenimiento": "Scripts de mantenimiento del sistema",
    }
    return nombres.get(ruta.name, "")


def _imports(ruta: Path) -> list[str]:
    """Módulos de OTRAS carpetas principales que esta carpeta importa."""
    conexiones: set[str] = set()
    for py in ruta.rglob("*.py"):
        if any(x in py.parts for x in EXCLUIR):
            continue
        try:
            texto = py.read_text(errors="ignore")
        except Exception:
            continue
        for m in re.findall(r"(?:from|import)\s+([a-z_][a-z0-9_.]*)", texto):
            raiz = m.split(".")[0]
            if raiz in RAICES and raiz != ruta.name:
                conexiones.add(raiz)
    return sorted(conexiones)


def _importado_por(ruta: Path, raiz: str) -> list[str]:
    """Carpetas que importan ESTA carpeta."""
    usados: set[str] = set()
    for otra in RAICES:
        if otra == raiz:
            continue
        otra_path = REPO / otra
        if not otra_path.exists():
            continue
        for py in otra_path.rglob("*.py"):
            if any(x in py.parts for x in EXCLUIR):
                continue
            try:
                texto = py.read_text(errors="ignore")
            except Exception:
                continue
            if re.search(rf"(?:from|import)\s+{re.escape(raiz)}\b", texto):
                usados.add(otra)
    return sorted(usados)


def main() -> int:
    usar_json = "--json" in sys.argv
    detalle = "--detalle" in sys.argv  # noqa: F841 — legacy/estable, sin cambio de comportamiento
    filas: list[dict] = []

    for raiz in RAICES:
        ruta = REPO / raiz
        if not ruta.exists():
            continue
        n_archivos = sum(
            1
            for p in ruta.rglob("*")
            if p.is_file()
            and p.suffix in {".py", ".sh", ".js", ".ts", ".md", ".json"}
            and not any(x in p.parts for x in EXCLUIR)
        )
        fila = {
            "carpeta": raiz,
            "creacion": _fecha_creacion(ruta),
            "modificacion": _fecha_mod(ruta),
            "archivos": n_archivos,
            "proposito": _proposito(ruta),
            "importa": _imports(ruta),
            "importada_por": _importado_por(ruta, raiz),
        }
        filas.append(fila)

    if usar_json:
        print(json.dumps(filas, indent=1, ensure_ascii=False))
        return 0

    # Salida markdown → docs/architecture/INVENTARIO_URA.md
    salida = [
        "# Inventario del sistema URA — árbol de carpetas (TASK-20260812-016)",
        "",
        f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')}",  # noqa: DTZ005 — legacy/estable, sin cambio de comportamiento
        "",
        "| Carpeta | Creada | Última mod. | Archivos | Propósito | Importa de | Importada por |",
        "|---------|--------|-------------|----------|-----------|------------|---------------|",
    ]
    for f in filas:
        salida.append(
            f"| {f['carpeta']} | {f['creacion'] or '—'} | {f['modificacion'] or '—'} "
            f"| {f['archivos']} | {f['proposito'] or '—'} "
            f"| {', '.join(f['importa']) or '—'} | {', '.join(f['importada_por']) or '—'} |"
        )
    salida += ["", "## Método árbol (tronco → ramas)", ""]
    salida += [
        "Orden de revisión por prioridad de valor (tronco primero, ramas después):",
        "",
        "1. **Tronco**: core, motor, knowledge, scripts/pro, monitor (núcleo del sistema)",
        "2. **Ramas principales**: agents, tests, deploy",
        "3. **Hojas**: docs, mantenimiento (soporte, al final)",
    ]
    salida.append("")
    destino = REPO / "docs" / "architecture" / "INVENTARIO_URA.md"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text("\n".join(salida), encoding="utf-8")
    print(f"INVENTARIO generado: {destino.relative_to(REPO)} ({len(filas)} carpetas)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""panel.py — Genera docs/planes/README.md con tabla de salud de planes/tareas.

Lee docs/udo/coordination.json y emite un panel Markdown con semáforos de estado,
responsables, revisor y métricas de calidad (gates, cobertura, seguridad).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DEFAULT_COORD = Path(__file__).resolve().parent.parent.parent / "docs" / "udo" / "coordination.json"
DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent.parent / "docs" / "planes" / "README.md"

SEMAFORO = {
    "cerrada": "🟢",
    "aprobada": "🟢",
    "terminado": "🟢",
    "done": "🟢",
    "en_progreso": "🟡",
    "en_revision": "🟡",
    "review": "🟡",
    "bloqueada": "🔴",
    "blocked": "🔴",
    "pendiente": "⚪",
    "planned": "⚪",
}


def cargar_coord(ruta: Path) -> dict:
    with ruta.open(encoding="utf-8") as f:
        return json.load(f)


def semaforo(estado: str) -> str:
    return SEMAFORO.get((estado or "").lower().replace("-", "_"), "⚪")


def valor_metrica(tarea: dict, clave: str) -> str:
    gates = tarea.get("ultimos_gates", {})
    if clave == "gates":
        if not gates:
            return "NO VERIFICADO"
        partes = []
        for nombre in ("ruff", "mypy", "pytest"):
            val = gates.get(nombre)
            if val:
                partes.append(f"{nombre}: {val}")
        return "; ".join(partes) if partes else "NO VERIFICADO"
    return tarea.get(clave, "NO VERIFICADO") or "NO VERIFICADO"


def generar_panel(datos: dict) -> str:
    colas = datos.get("colas", {})
    tareas = datos.get("tareas", {})

    orden = (
        colas.get("en_progreso", [])
        + colas.get("en_revision", [])
        + colas.get("bloqueadas", [])
        + colas.get("pendientes", [])
        + colas.get("aprobadas", [])
        + colas.get("cerradas", [])
    )
    vistos = set()
    filas = []
    for tid in orden:
        if tid in vistos or tid not in tareas:
            continue
        vistos.add(tid)
        t = tareas[tid]
        ejecutor = t.get("ejecutor") or "NO VERIFICADO"
        responsable = f"{ejecutor} {semaforo(t.get('estado', ''))}"
        filas.append(
            (
                tid,
                t.get("descripcion", "").replace("|", "\\|"),
                t.get("estado", ""),
                t.get("prioridad", ""),
                responsable,
                t.get("revisor") or "NO VERIFICADO",
                valor_metrica(t, "gates"),
                valor_metrica(t, "cobertura"),
                valor_metrica(t, "seguridad"),
                t.get("veredicto") or t.get("nota", "").replace("|", "\\|") or "NO VERIFICADO",
            )
        )

    lineas = [
        "# Panel de salud de planes y tareas",
        "",
        "_Generado automáticamente por `scripts/pro/panel.py`._",
        "",
        "| Plan/Task | Descripción | Estado | Prioridad | Responsable | Revisor | Últimos gates | Cobertura | Seguridad | Decisión pendiente |",
        "|-----------|-------------|--------|-----------|-------------|---------|---------------|-----------|-----------|--------------------|",
    ]
    for fila in filas:
        lineas.append("| " + " | ".join(fila) + " |")

    lineas.extend(
        [
            "",
            "## Leyenda",
            "",
            "- 🟢 Terminado / Aprobado",
            "- 🟡 En progreso / En revisión",
            "- 🔴 Bloqueado",
            "- ⚪ Pendiente",
            "",
            "## Modo análisis de planes",
            "",
            "Si recibes un mensaje que empieza con `Analiza este plan/proyecto según la metodología URA:`, "  # legacy/estable, sin cambio de comportamiento
            "estás en **MODO ANÁLISIS**. No ejecutes código. Solo lee, analiza y emite informe con "
            "puntos buenos, puntos malos, mejoras y veredicto **GO / GO CON CAMBIOS / NO-GO**. "
            "Registra el análisis en `docs/udo/coordination.json`.",
        ]
    )

    return "\n".join(lineas) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Genera panel de salud de planes/tareas")
    parser.add_argument("--coord", type=Path, default=DEFAULT_COORD, help="ruta a coordination.json")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="ruta de salida Markdown")
    args = parser.parse_args(argv)

    try:
        datos = cargar_coord(args.coord)
    except (OSError, ValueError) as e:
        print(f"ERROR: no se pudo leer {args.coord}: {e}", file=sys.stderr)
        return 1

    panel = generar_panel(datos)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(panel, encoding="utf-8")
    print(f"Panel generado en {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""panel.py — Genera docs/planes/README.md con salud de planes y tareas.

Lee docs/udo/coordination.json y los expedientes de tarea (opcionalmente) y
produce una tabla Markdown con semáforos:
  🟢 terminado / aprobado
  🟡 en progreso / en revisión
  🔴 bloqueado / cambios solicitados
  ⚪ pendiente / sin asignar

Cualquier métrica no medida se muestra como "NO VERIFICADO".
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_COORD = Path(__file__).resolve().parent.parent.parent / "docs" / "udo" / "coordination.json"
DEFAULT_OUT = Path(__file__).resolve().parent.parent.parent / "docs" / "planes" / "README.md"

SEMAFORO = {
    "aprobada": "🟢",
    "terminado": "🟢",
    "en_progreso": "🟡",
    "en_revision": "🟡",
    "cambios_solicitados": "🟡",
    "bloqueada": "🔴",
    "pendiente": "⚪",
}


def _valor(datos: dict, clave: str, defecto: str = "NO VERIFICADO") -> str:
    return datos.get(clave, defecto) or defecto


def _gate_resumen(tarea: dict) -> str:
    gates = tarea.get("gates") or {}
    if not gates:
        return "NO VERIFICADO"
    partes = []
    for nombre in ("ruff", "mypy", "pytest"):
        estado = gates.get(nombre, "NO VERIFICADO")
        partes.append(f"{nombre}: {estado}")
    return "; ".join(partes)


def _sem(estado: str) -> str:
    return SEMAFORO.get(estado.lower(), "⚪")


def generar_tabla(datos: dict) -> str:
    lineas = [
        "# Panel de salud de planes y tareas",
        "",
        f"_Generado automáticamente el {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} por `scripts/pro/panel.py`._",
        "",
        "| Plan/Task | Descripción | Estado | Prioridad | Responsable | Revisor | Últimos gates | Cobertura | Seguridad | Decisión pendiente |",
        "|-----------|-------------|--------|-----------|-------------|---------|---------------|-----------|-----------|--------------------|",
    ]

    tareas = datos.get("tareas", {})
    for tid in sorted(tareas):
        t = tareas[tid]
        estado = t.get("estado", "pendiente")
        responsable = t.get("ejecutor") or "NO ASIGNADO"
        revisor = t.get("revisor") or "NO ASIGNADO"
        cobertura = _valor(t, "cobertura")
        seguridad = _valor(t, "seguridad")
        decision = _valor(t, "decision_pendiente")
        if not decision and estado in {"pendiente", "bloqueada"}:
            decision = "Esperando asignación o desbloqueo"
        lineas.append(
            f"| {_sem(estado)} {tid} | {t.get('descripcion', '')} | {estado} | "
            f"{t.get('prioridad', 'baja')} | {responsable} | {revisor} | "
            f"{_gate_resumen(t)} | {cobertura} | {seguridad} | {decision} |"
        )

    lineas.extend([
        "",
        "## Leyenda",
        "",
        "- 🟢 Terminado / Aprobado",
        "- 🟡 En progreso / En revisión / Cambios solicitados",
        "- 🔴 Bloqueado",
        "- ⚪ Pendiente / Sin asignar",
        "",
        "## Agentes",
        "",
        "| Agente | Estado | Rol actual |",
        "|--------|--------|------------|",
    ])

    for agente, info in datos.get("agentes", {}).items():
        lineas.append(
            f"| {agente} | {info.get('estado', 'desconocido')} | {info.get('rol_actual') or '—'} |"
        )

    lineas.extend([
        "",
        "## Modo de operación",
        "",
        f"`{datos.get('modo', 'secuencial')}`",
        "",
    ])

    return "\n".join(lineas) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Genera panel de salud de planes")
    parser.add_argument("--coord", type=Path, default=DEFAULT_COORD, help="ruta a coordination.json")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="ruta de salida README.md")
    args = parser.parse_args(argv)

    try:
        with open(args.coord, encoding="utf-8") as f:
            datos = json.load(f)
    except (OSError, ValueError) as e:
        print(f"ERROR: no se pudo leer {args.coord}: {e}", file=sys.stderr)
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(generar_tabla(datos), encoding="utf-8")
    print(f"Panel generado: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""verify_protocol.py — Guardián de integridad del protocolo de coordinación.

Lee docs/udo/coordination.json y verifica invariantes:
  1. JSON válido con estructura esperada (modo, colas, agentes, tareas).
  2. Cada tarea aparece en exactamente una cola y tiene campos obligatorios.
  3. Toda tarea APROBADA tiene veredicto no vacío.
  4. No hay tareas EN_REVISION sin evidencia de revisión (nota o veredicto).
  5. Todo id en una cola existe en "tareas" y viceversa.

Uso:
    python3 scripts/pro/verify_protocol.py [--file ruta]

Salida: 0 si todo OK; 1 si hay violaciones (con mensajes a stderr).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent.parent / "docs" / "udo" / "coordination.json"

COLAS_VALIDAS = {"pendientes", "en_progreso", "en_revision", "aprobadas", "bloqueadas"}
CAMPOS_OBLIGATORIOS = {"descripcion", "ejecutor", "revisor", "estado", "prioridad"}


def cargar(ruta: Path) -> dict:
    """Carga coordination.json; lanza ValueError si no es JSON válido."""
    with ruta.open(encoding="utf-8") as f:
        return json.load(f)


def verificar(datos: dict) -> list[str]:
    """Devuelve lista de violaciones (vacía = protocolo íntegro)."""
    violaciones: list[str] = []

    if not isinstance(datos, dict):
        return ["raíz no es objeto JSON"]
    if "modo" not in datos or datos["modo"] not in {"secuencial", "paralelo"}:
        violaciones.append("campo 'modo' ausente o inválido (esperado secuencial|paralelo)")
    if "colas" not in datos or not isinstance(datos["colas"], dict):
        violaciones.append("campo 'colas' ausente o no es objeto")
        return violaciones
    colas = datos["colas"]
    for nombre in COLAS_VALIDAS:
        if nombre not in colas or not isinstance(colas[nombre], list):
            violaciones.append(f"cola '{nombre}' ausente o no es lista")
    if "tareas" not in datos or not isinstance(datos["tareas"], dict):
        violaciones.append("campo 'tareas' ausente o no es objeto")

    tareas = datos.get("tareas", {})
    ids_en_colas: set[str] = set()
    for cola, ids in colas.items():
        for tid in ids:
            if tid in ids_en_colas:
                violaciones.append(f"tarea {tid} duplicada en varias colas")
            ids_en_colas.add(tid)
            if tid not in tareas:
                violaciones.append(f"tarea {tid} en cola '{cola}' pero ausente en 'tareas'")

    for tid, tarea in tareas.items():
        if not isinstance(tarea, dict):
            violaciones.append(f"tarea {tid} no es objeto")
            continue
        for campo in CAMPOS_OBLIGATORIOS:
            if campo not in tarea:
                violaciones.append(f"tarea {tid} sin campo '{campo}'")
        estado = tarea.get("estado", "")
        if estado == "aprobada" and not tarea.get("veredicto"):
            violaciones.append(f"tarea {tid} APROBADA sin veredicto")
        if estado == "en_revision" and not (tarea.get("veredicto") or tarea.get("nota")):
            violaciones.append(f"tarea {tid} EN_REVISION sin evidencia de revisión")
        if tid not in ids_en_colas:
            violaciones.append(f"tarea {tid} no está en ninguna cola")

    for tid in ids_en_colas - set(tareas):
        violaciones.append(f"cola contiene tarea desconocida {tid}")

    return violaciones


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Guardián de integridad del protocolo de coordinación")
    parser.add_argument("--file", type=Path, default=DEFAULT_PATH, help="ruta a coordination.json")
    args = parser.parse_args(argv)

    try:
        datos = cargar(args.file)
    except (OSError, ValueError) as e:
        print(f"ERROR: no se pudo leer/parsear {args.file}: {e}", file=sys.stderr)
        return 1

    violaciones = verificar(datos)
    if violaciones:
        print(f"PROTOCOLO VIOLADO ({len(violaciones)}):", file=sys.stderr)
        for v in violaciones:
            print(f"  - {v}", file=sys.stderr)
        return 1

    print(f"OK: protocolo íntegro ({len(datos.get('tareas', {}))} tareas, modo {datos.get('modo')})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

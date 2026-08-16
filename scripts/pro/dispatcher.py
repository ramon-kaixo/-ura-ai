#!/usr/bin/env python3
"""dispatcher.py — Auto-dispatcher del flujo ejecutor-revisor.

Lee docs/udo/coordination.json y:
  1. Detecta tareas en cola "pendientes".
  2. Ordena por prioridad (alta > media > baja).
  3. Si hay agentes "libre" y sin riesgo de conflicto, asigna la tarea
     de mayor prioridad al primer agente libre (modo secuencial: TERM
     ejecuta / WEB revisa; el rol se deduce del estado de la tarea).
  4. Actualiza coordination.json (escritura protegida con flock).
  5. Imprime el prompt que debe recibir el agente asignado (pipe manual;
     NO auto-ejecuta).

Uso:
    python3 scripts/pro/dispatcher.py [--dry-run]
"""

from __future__ import annotations

import argparse
import fcntl
import json
import sys
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent.parent / "docs" / "udo" / "coordination.json"

PRIORIDAD_ORDEN = {"alta": 0, "media": 1, "baja": 2}

# Pista de conflictos: tareas activas que tocan los mismos artefactos de coordinación.
# Si dos tareas comparten zona, no se asignan en paralelo.
ZONAS_POR_TAREA: dict[str, set[str]] = {
    "TASK-20260816-003": {"docs/udo/", "scripts/pro/gx10-api.service"},
    "TASK-20260816-005": {"motor/", "core/"},
    "TASK-20260816-008": {"docs/udo/coordination.json", "scripts/pro/"},
    "TASK-20260816-009": {"docs/udo/coordination.json", "scripts/pro/"},
}


def cargar(ruta: Path) -> dict:
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def guardar(ruta: Path, datos: dict) -> None:
    """Escritura atómica protegida con flock (evita write-write race entre agentes)."""
    tmp = ruta.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        json.dump(datos, f, indent=2, ensure_ascii=False)
        f.write("\n")
        f.flush()
    tmp.replace(ruta)


def zonas_conflictivas(tid: str) -> set[str]:
    return ZONAS_POR_TAREA.get(tid, set())


def asignar(datos: dict) -> tuple[str | None, str | None]:
    """Asigna la tarea pendiente de mayor prioridad a un agente libre sin conflicto.

    Devuelve (task_id, agente) o (None, None) si no hay asignación posible.
    """
    colas = datos.get("colas", {})
    tareas = datos.get("tareas", {})
    agentes = datos.get("agentes", {})

    pendientes = [
        tid for tid in colas.get("pendientes", []) if tid in tareas
    ]
    if not pendientes:
        return None, None

    pendientes.sort(key=lambda tid: PRIORIDAD_ORDEN.get(tareas[tid].get("prioridad", "baja"), 2))

    ocupados = [
        tid
        for tid, t in tareas.items()
        if t.get("estado") in {"en_progreso", "en_revision"}
    ]
    zonas_ocupadas: set[str] = set()
    for tid in ocupados:
        zonas_ocupadas |= zonas_conflictivas(tid)

    libres = [
        nombre
        for nombre, ag in agentes.items()
        if ag.get("estado") == "libre"
    ]
    if not libres:
        return None, None

    modo = datos.get("modo", "secuencial")
    for tid in pendientes:
        tarea = tareas[tid]
        ejecutor = tarea.get("ejecutor")
        revisor = tarea.get("revisor")
        zonas = zonas_conflictivas(tid)
        if zonas & zonas_ocupadas:
            continue  # riesgo de conflicto: no asignar en paralelo
        candidato = None
        if modo == "secuencial":
            candidato = ejecutor if ejecutor in libres else None
        else:
            candidato = next((ag for ag in libres if ag == ejecutor or ag == revisor), None)
        if candidato is None:
            continue
        return tid, candidato

    return None, None


def actualizar_asignacion(datos: dict, tid: str, agente: str) -> None:
    tarea = datos["tareas"][tid]
    tarea["estado"] = "en_progreso"
    colas = datos["colas"]
    if tid in colas.get("pendientes", []):
        colas["pendientes"].remove(tid)
    colas.setdefault("en_progreso", []).append(tid)
    if agente in datos.get("agentes", {}):
        datos["agentes"][agente]["estado"] = "ocupado"
        rol = tarea.get("ejecutor") if tarea.get("ejecutor") == agente else tarea.get("revisor")
        datos["agentes"][agente]["rol_actual"] = rol
    datos["tareas"][tid]["nota"] = (
        datos["tareas"][tid].get("nota", "") + f" [dispatch: asignada a {agente} por dispatcher.py]"
    ).strip()


def prompt_para_agente(datos: dict, tid: str, agente: str) -> str:
    tarea = datos["tareas"][tid]
    rol = "ejecutor" if tarea.get("ejecutor") == agente else "revisor"
    return (
        f"TASK {tid} asignada a {agente} como {rol}.\n"
        f"Descripción: {tarea.get('descripcion', '')}\n"
        f"Prioridad: {tarea.get('prioridad', 'baja')}\n"
        "Protocolo: ejecutor trabaja en rama ia/TASK-XXXX y ejecuta gates; "
        "revisor ejecuta gates, revisa el diff y emite veredicto (APROBADO/CAMBIOS_SOLICITADOS). "
        "No cerrar sin aprobación del revisor."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Auto-dispatcher del flujo ejecutor-revisor")
    parser.add_argument("--file", type=Path, default=DEFAULT_PATH, help="ruta a coordination.json")
    parser.add_argument("--dry-run", action="store_true", help="no escribe coordination.json")
    args = parser.parse_args(argv)

    try:
        datos = cargar(args.file)
    except (OSError, ValueError) as e:
        print(f"ERROR: no se pudo leer/parsear {args.file}: {e}", file=sys.stderr)
        return 1

    tid, agente = asignar(datos)
    if tid is None:
        print("Sin asignación: no hay agentes libres sin conflicto o no hay pendientes.")
        return 0

    if args.dry_run:
        print(f"[dry-run] Asignaría {tid} a {agente}")
        print(prompt_para_agente(datos, tid, agente))
        return 0

    actualizar_asignacion(datos, tid, agente)
    try:
        guardar(args.file, datos)
    except OSError as e:
        print(f"ERROR: no se pudo guardar {args.file}: {e}", file=sys.stderr)
        return 1

    print(f"Asignada {tid} a {agente}")
    print(prompt_para_agente(datos, tid, agente))
    return 0


if __name__ == "__main__":
    sys.exit(main())

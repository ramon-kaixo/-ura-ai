#!/usr/bin/env python3
"""audit_cierre_udo.py — Audita cierres UDO sin gate de integridad (A5, TASK-20260818-007).

Detecta tareas en coordination.json con estado aprobada/cerrada que NO
tienen expediente .md con `commits:` y `commit_base:` registrados (el cierre
se hizo por edición manual del JSON, saltándose el gate `_gate_revision`
de ura-udo, como ocurrió con TASK-20260817-031 el 2026-08-17).

Read-only: no modifica nada. Salida: lista de cierres sin gate.
Exit code: 0 = todo OK; 1 = hay cierres sin gate.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

UDO_ROOT = Path(__file__).resolve().parent.parent.parent / "docs" / "udo"
TASKS_DIR = UDO_ROOT / "tasks"
COORD = UDO_ROOT / "coordination.json"

ESTADOS_CERRADOS = {"aprobada", "cerrada", "DONE"}


def _campo(expediente: Path, campo: str) -> str:
    for linea in expediente.read_text(encoding="utf-8").splitlines():
        if linea.startswith(f"{campo}:"):
            return linea.split(":", 1)[1].strip()
    return ""


def audit() -> tuple[list[str], list[str]]:
    coord = json.loads(COORD.read_text(encoding="utf-8"))
    errores: list[str] = []
    info: list[str] = []
    for tid, tarea in coord.get("tareas", {}).items():
        if tarea.get("estado") not in ESTADOS_CERRADOS:
            continue
        exp = TASKS_DIR / f"{tid}.md"
        if not exp.exists():
            errores.append(f"{tid}: sin expediente .md (estado {tarea.get('estado')})")
            continue
        commits = _campo(exp, "commits")
        base = _campo(exp, "commit_base")
        if not commits or commits == "[]":
            errores.append(f"{tid}: expediente sin commits: registrados")
        if not base or base == "unknown":
            info.append(f"{tid}: sin commit_base (pre-parche, X2 no retroactivo)")
    return errores, info


def main() -> int:
    errores, info = audit()
    if errores:
        print(f"AUDITORIA: {len(errores)} cierre(s) sin gate de integridad:")
        for e in errores:
            print(f"  - {e}")
    if info:
        print(f"INFO: {len(info)} expediente(s) pre-parche sin commit_base (X2, no retroactivo)")
    if not errores and not info:
        total = len(json.loads(COORD.read_text(encoding="utf-8"))["tareas"])
        print(f"AUDITORIA: OK — {total} tareas revisadas, 0 cierres sin gate")
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main())

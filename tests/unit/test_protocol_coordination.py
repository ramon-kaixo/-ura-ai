"""Tests de alto nivel del protocolo de coordinación (coordination.json).

Verifican invariantes del registro compartido sin depender de la
implementación interna de verify_protocol.py / dispatcher.py.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
COORD = ROOT / "docs" / "udo" / "coordination.json"


def _load_coord() -> dict[str, Any]:
    with COORD.open(encoding="utf-8") as f:
        return json.load(f)


def test_coordination_json_es_valido() -> None:
    datos = _load_coord()
    assert "modo" in datos
    assert "colas" in datos
    assert "tareas" in datos
    assert "agentes" in datos


def test_cada_tarea_esta_en_exactamente_una_cola() -> None:
    datos = _load_coord()
    tareas = set(datos["tareas"])
    vistas: set[str] = set()
    for cola, ids in datos["colas"].items():
        assert isinstance(ids, list), f"cola {cola} no es lista"
        for tid in ids:
            assert tid in tareas, f"{tid} en cola {cola} no existe en tareas"
            assert tid not in vistas, f"{tid} duplicado en colas"
            vistas.add(tid)
    for tid in tareas:
        assert tid in vistas, f"{tid} no está en ninguna cola"


def test_tareas_aprobadas_tienen_veredicto() -> None:
    datos = _load_coord()
    for tid in datos["colas"].get("aprobadas", []):
        tarea = datos["tareas"][tid]
        assert tarea.get("veredicto"), f"{tid} aprobada sin veredicto"


def test_tareas_en_revision_tienen_evidencia() -> None:
    datos = _load_coord()
    for tid in datos["colas"].get("en_revision", []):
        tarea = datos["tareas"][tid]
        assert tarea.get("veredicto") or tarea.get("nota"), f"{tid} en_revision sin veredicto ni nota"


def test_agentes_tienen_estado_y_rol() -> None:
    datos = _load_coord()
    for agente, info in datos["agentes"].items():
        assert "estado" in info, f"{agente} sin estado"
        assert "rol_actual" in info, f"{agente} sin rol_actual"


def test_no_hay_import_inverso_motor_core() -> None:
    res = subprocess.run(
        ["grep", "-rE", "from core|import core", "--include=*.py", "motor/"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode != 0, f"Quedan imports motor→core:\n{res.stdout}"


def test_verify_protocol_pasa_con_coordination_actual() -> None:
    res = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "pro" / "verify_protocol.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, res.stderr

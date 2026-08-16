"""Tests para scripts/pro/panel.py."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.pro.panel import cargar_coord, generar_panel, semaforo

ROOT = Path(__file__).resolve().parent.parent.parent
COORD = ROOT / "docs" / "udo" / "coordination.json"


def test_semaforo_mapea_estados() -> None:
    assert semaforo("cerrada") == "🟢"
    assert semaforo("aprobada") == "🟢"
    assert semaforo("en_progreso") == "🟡"
    assert semaforo("en_revision") == "🟡"
    assert semaforo("bloqueada") == "🔴"
    assert semaforo("pendiente") == "⚪"
    assert semaforo("desconocido") == "⚪"


def test_cargar_coord() -> None:
    datos = cargar_coord(COORD)
    assert "colas" in datos
    assert "tareas" in datos
    assert "modo" in datos


def test_generar_panel_contiene_tabla_y_semaforos() -> None:
    datos = cargar_coord(COORD)
    panel = generar_panel(datos)
    assert "# Panel de salud de planes y tareas" in panel
    assert "| Plan/Task |" in panel
    assert "🟢" in panel or "🟡" in panel or "⚪" in panel
    assert "Modo análisis de planes" in panel


def test_generar_panel_no_verificado_para_metricas_faltantes() -> None:
    datos = {
        "modo": "secuencial",
        "colas": {"pendientes": ["TASK-TEST"], "en_progreso": [], "en_revision": [], "aprobadas": [], "bloqueadas": [], "cerradas": []},
        "agentes": {},
        "tareas": {
            "TASK-TEST": {
                "descripcion": "Tarea de prueba",
                "estado": "pendiente",
                "prioridad": "baja",
                "ejecutor": "TERM",
                "revisor": "WEB",
            }
        },
    }
    panel = generar_panel(datos)
    assert "NO VERIFICADO" in panel


def test_main_genera_archivo(tmp_path: Path) -> None:
    from scripts.pro.panel import main

    coord = tmp_path / "coordination.json"
    output = tmp_path / "README.md"
    coord.write_text(json.dumps({
        "modo": "secuencial",
        "colas": {"pendientes": [], "en_progreso": [], "en_revision": [], "aprobadas": [], "bloqueadas": [], "cerradas": []},
        "agentes": {},
        "tareas": {},
    }), encoding="utf-8")

    rc = main(["--coord", str(coord), "--output", str(output)])
    assert rc == 0
    assert output.exists()
    assert "Panel de salud" in output.read_text(encoding="utf-8")

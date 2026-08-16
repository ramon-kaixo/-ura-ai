"""Tests para la sección 'Modo análisis de planes' de AGENTS.md."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
AGENTS = ROOT / "AGENTS.md"


def _section() -> str:
    text = AGENTS.read_text(encoding="utf-8")
    match = re.search(r"## Modo análisis de planes.*?\n(?=## |\Z)", text, re.DOTALL)
    assert match, "Sección 'Modo análisis de planes' no encontrada en AGENTS.md"
    return match.group(0)


def test_seccion_existe() -> None:
    section = _section()
    assert "TASK-20260816-010" in section


def test_trigger_documentado() -> None:
    section = _section()
    assert 'empieza con "Analiza este plan/proyecto según la metodología URA:"' in section


def test_no_ejecutar_codigo() -> None:
    section = _section()
    assert "No ejecutes código" in section


def test_veredictos_documentados() -> None:
    section = _section()
    assert "GO" in section
    assert "GO CON CAMBIOS" in section
    assert "NO-GO" in section


def test_registro_en_coordination_json() -> None:
    section = _section()
    assert "docs/udo/coordination.json" in section
    assert "veredicto" in section


def test_detectar_mensaje_modo_analisis() -> None:
    trigger = "Analiza este plan/proyecto según la metodología URA:"
    assert trigger.startswith("Analiza este plan/proyecto según la metodología URA:")

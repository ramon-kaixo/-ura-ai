"""Constantes compartidas del sistema multi-agente."""

from __future__ import annotations

import os
from pathlib import Path

URA_ROOT = Path(os.environ.get("URA_ROOT", "/home/ramon/URA/ura_ia_1972"))
SCRIPTS = URA_ROOT / "scripts/pro"
NERVIOSO = URA_ROOT / ".nervioso"
MAX_CICLO_S = 300

MODELOS: dict[str, str] = {
    "orquestador": "qwen2.5-coder:14b",
    "ejecutor": "deepseek-coder:6.7b",
    "reparador_rapido": "deepseek-coder:6.7b",
    "reparador_potente": "qwen3:32b-q8_0",
    "revisor": "qwen2.5-coder:14b-instruct-q8_0",
}

RUFF = str(URA_ROOT / ".venv/bin/ruff")

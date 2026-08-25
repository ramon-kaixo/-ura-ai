"""Constantes compartidas del sistema multi-agente.

URA_ROOT y rutas derivadas provienen de shared.paths (fuente canónica).
"""

from __future__ import annotations

from shared.paths import URA_ROOT

__all__ = [
    "MAX_CICLO_S",
    "MODELOS",
    "NERVIOSO",
    "RUFF",
    "SCRIPTS",
    "URA_ROOT",
]

MAX_CICLO_S = 300

MODELOS: dict[str, str] = {
    "orquestador": "qwen3.6:27b",
    "ejecutor": "qwen3-coder:30b",
    "reparador_rapido": "qwen3-coder:30b",
    "reparador_potente": "qwen3.6:27b",
    "revisor": "qwen3.6:27b",
}

NERVIOSO = URA_ROOT / ".nervioso"
SCRIPTS = URA_ROOT / "scripts/pro"
RUFF = str(URA_ROOT / ".venv/bin/ruff")

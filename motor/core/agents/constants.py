"""Constantes compartidas del sistema multi-agente.

URA_ROOT y rutas derivadas provienen de shared.paths (fuente canónica).
"""

from __future__ import annotations

from shared.paths import URA_ROOT

MAX_CICLO_S = 300

MODELOS: dict[str, str] = {
    "orquestador": "qwen2.5-coder:14b",
    "ejecutor": "deepseek-coder:6.7b",
    "reparador_rapido": "deepseek-coder:6.7b",
    "reparador_potente": "qwen3:32b-q8_0",
    "revisor": "qwen2.5-coder:14b-instruct-q8_0",
}

NERVIOSO = URA_ROOT / ".nervioso"
SCRIPTS = URA_ROOT / "scripts/pro"
RUFF = str(URA_ROOT / ".venv/bin/ruff")

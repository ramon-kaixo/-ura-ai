#!/usr/bin/env python3
"""
Settings Loader - Paso 3A
──────────────────────────
Carga y guardado de configuración.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def load_config(config_path: Path | None = None) -> dict:
    """
    Cargar configuración desde archivo.

    Args:
        config_path: Ruta al archivo de configuración (opcional)

    Returns:
        Dict con configuración cargada
    """
    if config_path is None:
        config_path = Path(__file__).parent.parent / "config" / "settings.json"

    default_config = {
        "ollama_port": 11434,
        "ollama_host": "localhost",
        "auto_start_ollama": True,
        "auto_start_windsurf": True,
        "auto_close_on_exit": False,
        "preferred_model": "qwen2.5:3b-instruct",
        "project_path": str(Path.home()),
        "check_interval": 5,
        "voice_enabled": True,
        "interaction_mode": "no_cursor",
        "cursor_speed": 0.5,
    }

    try:
        if config_path.exists():
            with open(config_path) as f:
                user_config = json.load(f)
            default_config.update(user_config)
    except Exception as e:
        logger.warning(f"No se pudo cargar configuración: {e}")

    return default_config


def save_config(window):
    """Guardar configuración a settings.json."""
    try:
        config_dir = Path(__file__).parent
        config_dir.mkdir(exist_ok=True)

        config_file = config_dir / "settings.json"
        with open(config_file, "w") as f:
            json.dump(window.config, f, indent=2)
        logger.info("Configuración guardada en settings.json")
    except Exception as e:
        logger.error(f"Error guardando configuración: {e}")

#!/usr/bin/env python3
"""
Automation Utils - Paso 3A
───────────────────────────
Utilidades para automatización visual y comandos.
"""

import logging

logger = logging.getLogger(__name__)


def _handle_windsurf_command(window, message: str):
    """Manejar comando de Windsurf."""
    from handlers.windsurf_handler import handle_windsurf_command

    handle_windsurf_command(window, message)


def _handle_visual_automation(window, message: str):
    """Manejar comando de automatización visual con modo autónomo."""
    from handlers.vision_handler import handle_visual_automation

    handle_visual_automation(window, message)


def auto_start_services(window):
    """Arranque automático de servicios."""
    try:
        if window.config.get("auto_start_windsurf"):
            window.start_windsurf()
    except Exception as e:
        logger.error(f"Error en auto_start_services: {e}")

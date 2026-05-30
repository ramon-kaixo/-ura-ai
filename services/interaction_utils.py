#!/usr/bin/env python3
"""
Interaction Utils - Paso 3A
─────────────────────────────
Utilidades para modos de interacción.
"""

import logging

logger = logging.getLogger(__name__)


def change_interaction_mode(window, mode):
    """Cambiar modo de interacción (cursor, voz, etc.)"""
    window.config["interaction_mode"] = mode
    logger.info(f"Modo de interacción cambiado a: {mode}")

    if mode == "no_cursor":
        window.speed_slider.hide()
    elif mode == "with_cursor":
        window.speed_slider.show()

    window.save_config()
    logger.info(f"Modo de interacción: {mode}")

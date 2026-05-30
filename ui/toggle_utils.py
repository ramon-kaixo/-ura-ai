#!/usr/bin/env python3
"""
Toggle Utils - Paso 3A
──────────────────────
Utilidades para toggles y paneles.
"""

import logging

logger = logging.getLogger(__name__)


def toggle_windsurf_panel(window):
    """Colapsar/expandir el panel izquierdo de Windsurf."""
    sizes = window.main_splitter.sizes()
    if sizes[0] > 0:
        window._last_windsurf_width = sizes[0]
        new_sizes = [0, sizes[1] + sizes[0], sizes[2]]
        window.windsurf_collapse_btn.setText("➡")
        window.windsurf_collapse_btn.setToolTip("Expandir panel de Windsurf")
    else:
        restore = window._last_windsurf_width or 400
        new_sizes = [restore, max(100, sizes[1] - restore), sizes[2]]
        window.windsurf_collapse_btn.setText("⬅")
        window.windsurf_collapse_btn.setToolTip("Colapsar panel de Windsurf")
    window.main_splitter.setSizes(new_sizes)
    logger.info(f"Panel Windsurf {'colapsado' if sizes[0] > 0 else 'expandido'}")


def toggle_turbo_mode(window):
    """Alternar modo turbo (concurrente)."""
    window.config["turbo_mode"] = not window.config.get("turbo_mode", False)
    status = "activado" if window.config["turbo_mode"] else "desactivado"
    window.chat_alert(f"Modo turbo {status}")
    logger.info(f"Modo turbo {status}")


def toggle_continuous_conversation(window):
    """Iniciar/detener conversación continua por voz."""
    if not window.continuous_conversation:
        window.chat_alert(
            "Conversación continua no disponible. Requiere SpeechRecognition y síntesis de voz."
        )
        return

    window.continuous_conversation = not window.continuous_conversation
    status = "activada" if window.continuous_conversation else "desactivada"
    window.chat_alert(f"Conversación continua {status}")
    logger.info(f"Conversación continua {status}")


def show_ollama_error(window, error_message):
    """Mostrar error de Ollama en UI."""
    window.chat_alert(f"Error Ollama: {error_message}")
    logger.error(f"Error Ollama: {error_message}")

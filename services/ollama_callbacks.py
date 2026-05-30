#!/usr/bin/env python3
"""
Ollama Callbacks - Paso 3A
───────────────────────────
Callbacks para eventos de Ollama.
"""

import logging
import time

logger = logging.getLogger(__name__)


def on_ollama_dropped(window):
    """Mostrar aviso en el chat cuando Ollama se cae."""
    timestamp = time.strftime("%H:%M:%S")
    window.ura_history_text.append(
        f"<span style='color: #dc3545;'>[{timestamp}] ⚠️ Ollama se ha caído. Relanzando automáticamente...</span>"
    )
    # Auto-scroll

    cursor = window.ura_history_text.textCursor()
    cursor.movePosition(cursor.End)
    window.ura_history_text.setTextCursor(cursor)

    window.is_reconnecting = True
    logger.warning("Ollama se ha caído, iniciando reconexión")


def on_ollama_recovered(window):
    """Mostrar aviso en el chat cuando Ollama se recupera."""
    timestamp = time.strftime("%H:%M:%S")
    window.ura_history_text.append(
        f"<span style='color: #28a745;'>[{timestamp}] ✅ Ollama se ha recuperado.</span>"
    )
    # Auto-scroll

    cursor = window.ura_history_text.textCursor()
    cursor.movePosition(cursor.End)
    window.ura_history_text.setTextCursor(cursor)

    window.is_reconnecting = False
    logger.info("Ollama se ha recuperado")


def show_ollama_error(window, error_message):
    """Mostrar mensaje de error de Ollama."""
    logger.warning(error_message)
    if not window.ollama_status:
        window.user_input.setPlaceholderText(f"Ollama: {error_message}")

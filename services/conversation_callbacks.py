#!/usr/bin/env python3
"""
Conversation Callbacks - Paso 3A
────────────────────────────────
Callbacks para conversación continua.
"""

import logging

logger = logging.getLogger(__name__)


def on_continuous_user_text(window, text):
    """Callback cuando se recibe texto del usuario en conversación continua."""
    window.current_user_message = text
    window.chat_user(text)
    logger.info(f"Texto continuo recibido: {text[:50]}...")


def on_continuous_ura_response(window, response):
    """Callback cuando se recibe respuesta de URA en conversación continua."""
    window.chat_ura(response)
    # Auto-scroll

    cursor = window.ura_history_text.textCursor()
    cursor.movePosition(cursor.End)
    window.ura_history_text.setTextCursor(cursor)
    logger.info(f"Respuesta continua recibida: {response[:50]}...")


def on_conversation_status(window, status):
    """Callback cuando cambia el estado de la conversación continua."""
    window.chat_alert(f"Estado conversación: {status}")
    logger.info(f"Estado conversación: {status}")

#!/usr/bin/env python3
"""
Voice Utils - Paso 3A
──────────────────────
Utilidades para entrada de voz.
"""

import logging

logger = logging.getLogger(__name__)


def start_voice_input(window):
    """Iniciar dictado por voz funcional."""

    if not window.voice_recognizer:
        window.chat_alert("Reconocimiento de voz no disponible")
        return

    window.mic_button.setStyleSheet(
        """
        QPushButton {
            background-color: #ffc107;
            color: #000;
            border: none;
            border-radius: 16px;
            font-size: 16px;
            font-weight: bold;
        }
    """
    )

    window.voice_recognizer.start_listening()
    window.user_input.setPlaceholderText("Escuchando... habla ahora")
    logger.info("Iniciando entrada de voz")

#!/usr/bin/env python3
"""
Voice Callbacks - Paso 3A
────────────────────────
Callbacks para reconocimiento de voz y TTS.
"""

import logging

logger = logging.getLogger(__name__)


def on_voice_recognized(window, text):
    """Manejar texto reconocido."""
    if text == "Escuchando...":
        return

    # Restaurar botón
    window.mic_button.setStyleSheet("""
        QPushButton {
            background-color: #007bff;
            color: white;
            border: none;
            border-radius: 16px;
            font-size: 16px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #0056b3;
        }
    """)

    # Detectar comando especial de salud
    if "informe de salud" in text.lower() or "health report" in text.lower():
        window.handle_health_report_command()
        return

    # Añadir texto al input
    current_text = window.user_input.text()
    new_text = current_text + " " + text if current_text else text

    window.user_input.setText(new_text)
    window.user_input.setPlaceholderText("Escribe tu mensaje aquí para Ura...")


def on_voice_error(window, error):
    """Manejar error de voz."""
    window.chat_alert(f"Error de voz: {error}")
    window.mic_button.setStyleSheet("""
        QPushButton {
            background-color: #dc3545;
            color: white;
            border: none;
            border-radius: 16px;
            font-size: 16px;
            font-weight: bold;
        }
    """)


def on_speech_started(window):
    """Callback cuando empieza a hablar TTS."""
    window.generation_active = True
    window.send_button.setEnabled(False)
    window.send_button.setText("🔊 Hablando...")


def on_speech_finished(window):
    """Callback cuando termina de hablar TTS."""
    window.generation_active = False
    window.send_button.setEnabled(True)
    window.send_button.setText("Enviar")

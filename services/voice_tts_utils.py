#!/usr/bin/env python3
"""
Voice TTS Utils - Paso 3A
──────────────────────────
Utilidades para síntesis de voz (TTS).
"""

import logging

logger = logging.getLogger(__name__)


def voice_notify_issues(window, message):
    """Notificar problemas por voz."""
    # Mostrar en UI
    import time

    timestamp = time.strftime("%H:%M:%S")
    window.ura_history_text.append(f"[{timestamp}] ⚠️ {message}")

    # Sintetizar por voz si está disponible
    from services.threads import TTS_AVAILABLE, GTTS_AVAILABLE, TextToSpeechThread

    if TTS_AVAILABLE or GTTS_AVAILABLE:
        if not window.tts_engine:
            window.tts_engine = TextToSpeechThread()
            window.tts_engine.speaking_started.connect(window.on_speech_started)
            window.tts_engine.speaking_finished.connect(window.on_speech_finished)
            window.tts_engine.error_occurred.connect(window.on_voice_error)

        window.tts_engine.speak(message)

    logger.warning(f"Notificación de problemas: {message}")


def speak_response(window):
    """Leer última respuesta de URA en voz alta."""
    from services.threads import TTS_AVAILABLE, GTTS_AVAILABLE
    from PyQt5.QtWidgets import QMessageBox

    if not (TTS_AVAILABLE or GTTS_AVAILABLE):
        QMessageBox.warning(
            window,
            "Error",
            "Síntesis de voz no disponible. Instala con: pip install pyttsx3 o pip install gTTS playsound",
        )
        return

    # Obtener última respuesta de URA
    response_text = window.ura_pending_text.toPlainText().strip()
    if not response_text:
        QMessageBox.information(window, "Información", "No hay respuesta de URA para leer")
        return

    if not window.tts_engine:
        from services.threads import TextToSpeechThread

        window.tts_engine = TextToSpeechThread()
        window.tts_engine.speaking_started.connect(window.on_speech_started)
        window.tts_engine.speaking_finished.connect(window.on_speech_finished)
        window.tts_engine.error_occurred.connect(window.on_voice_error)

    window.tts_engine.speak(response_text)

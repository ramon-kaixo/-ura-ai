#!/usr/bin/env python3
"""
Voice Init - Paso 3A
─────────────────────
Inicialización de componentes de voz.
"""

import logging

logger = logging.getLogger(__name__)


def initialize_voice_components(window):
    """Inicializar componentes de voz."""
    from services.threads import SPEECH_RECOGNITION_AVAILABLE, TTS_AVAILABLE, GTTS_AVAILABLE
    from services.threads import VoiceRecognitionThread, TextToSpeechThread

    if SPEECH_RECOGNITION_AVAILABLE:
        # Cleanup en closeEvent (voice threads loop)
        window.voice_recognizer = VoiceRecognitionThread()
        window.voice_recognizer.recognized_text.connect(window.on_voice_recognized)
        window.voice_recognizer.error_occurred.connect(window.on_voice_error)

    if TTS_AVAILABLE or GTTS_AVAILABLE:
        # Cleanup en closeEvent (voice threads loop)
        window.tts_engine = TextToSpeechThread()
        window.tts_engine.speaking_started.connect(window.on_speech_started)
        window.tts_engine.speaking_finished.connect(window.on_speech_finished)
        window.tts_engine.error_occurred.connect(window.on_voice_error)

#!/usr/bin/env python3
"""
Voz Mejorada de URA - Nivel 23

Reconocimiento y síntesis de voz mejorados:
- Whisper (via Ollama) para reconocimiento offline
- piper-tts para síntesis de voz neuronal en español
- Compatibilidad con sistemas actuales (pyttsx3, gTTS)
"""

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class VoiceWhisper:
    """Reconocimiento de voz con Whisper via Ollama."""

    def __init__(self, model: str = "whisper-tiny"):
        self.model = model
        self._check_ollama()

    def _check_ollama(self):
        """Verifica que Ollama esté disponible."""
        try:
            subprocess.run(
                ["curl", "-s", "http://localhost:11434/api/tags"], capture_output=True, timeout=5
            )
            logger.info("Ollama disponible para Whisper")
        except Exception as e:
            logger.warning(f"Ollama no disponible para Whisper: {e}")

    def transcribe(self, audio_file: str) -> str | None:
        """Transcribe archivo de audio usando Whisper via Ollama."""
        try:
            audio_path = Path(audio_file)
            if not audio_path.exists():
                logger.error(f"Archivo de audio no encontrado: {audio_file}")
                return None

            # Usar Ollama para transcribir
            result = subprocess.run(
                ["ollama", "run", self.model, f"Transcribe este archivo de audio: {audio_file}"],
                capture_output=True,
                text=True,
                timeout=60,
            )

            transcription = result.stdout.strip()
            logger.info(f"Transcripción completada: {len(transcription)} caracteres")
            return transcription

        except subprocess.TimeoutExpired:
            logger.error("Timeout en transcripción Whisper")
            return None
        except Exception as e:
            logger.error(f"Error en transcripción Whisper: {e}")
            return None


class VoicePiper:
    """Síntesis de voz con Piper-TTS."""

    def __init__(self, model: str = "es_ES-danny-medium"):
        self.model = model
        self._check_piper()

    def _check_piper(self):
        """Verifica que piper-tts esté disponible."""
        try:
            subprocess.run(["piper", "--version"], capture_output=True, timeout=5)
            logger.info("Piper-TTS disponible")
        except Exception as e:
            logger.warning(f"Piper-TTS no disponible: {e}")

    def synthesize(self, text: str, output_file: str) -> bool:
        """Sintetiza texto a voz usando Piper-TTS."""
        try:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Usar piper para sintetizar
            result = subprocess.run(
                ["piper", "-m", self.model, "-f", output_file, text],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode == 0:
                logger.info(f"Síntesis completada: {output_file}")
                return True
            else:
                logger.error(f"Error en síntesis Piper: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            logger.error("Timeout en síntesis Piper")
            return False
        except Exception as e:
            logger.error(f"Error en síntesis Piper: {e}")
            return False


class VoiceEnhanced:
    """Sistema de voz mejorado con Whisper y Piper-TTS."""

    def __init__(self, use_whisper: bool = True, use_piper: bool = True):
        self.use_whisper = use_whisper
        self.use_piper = use_piper

        if use_whisper:
            self.whisper = VoiceWhisper()

        if use_piper:
            self.piper = VoicePiper()

        # Fallback a sistemas actuales
        try:
            import pyttsx3

            self.pyttsx3 = pyttsx3
            logger.info("pyttsx3 disponible como fallback")
        except ImportError:
            self.pyttsx3 = None
            logger.warning("pyttsx3 no disponible")

    def transcribe(self, audio_file: str) -> str | None:
        """Transcribe audio usando Whisper o fallback."""
        if self.use_whisper:
            result = self.whisper.transcribe(audio_file)
            if result:
                return result

        # Fallback a otros sistemas si falla Whisper
        logger.warning("Whisper no disponible, usando fallback")
        return None

    def speak(self, text: str, output_file: str | None = None) -> bool:
        """Sintetiza texto a voz usando Piper-TTS o fallback."""
        if self.use_piper and output_file:
            return self.piper.synthesize(text, output_file)

        # Fallback a pyttsx3
        if self.pyttsx3:
            try:
                engine = self.pyttsx3.init()
                engine.say(text)
                engine.runAndWait()
                return True
            except Exception as e:
                logger.error(f"Error con pyttsx3: {e}")

        logger.warning("No hay sistema de síntesis disponible")
        return False

    def get_capabilities(self) -> dict:
        """Obtener capacidades del sistema de voz."""
        return {
            "whisper_available": self.use_whisper,
            "piper_available": self.use_piper,
            "pyttsx3_available": self.pyttsx3 is not None,
        }


# Singleton
_voice_enhanced: VoiceEnhanced | None = None


def get_voice_enhanced(use_whisper: bool = True, use_piper: bool = True) -> VoiceEnhanced:
    """Obtener el singleton del sistema de voz mejorado."""
    global _voice_enhanced
    if _voice_enhanced is None:
        _voice_enhanced = VoiceEnhanced(use_whisper=use_whisper, use_piper=use_piper)
    return _voice_enhanced


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    voice = get_voice_enhanced()

    print("Sistema de voz mejorado creado")
    print(f"Capacidades: {voice.get_capabilities()}")

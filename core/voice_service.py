#!/usr/bin/env python3
"""
Voice Service - Fase 6
Transcripción con Whisper (Ollama) y síntesis con piper-tts.
"""

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class VoiceService:
    """Servicio de voz con transcripción y síntesis."""

    def __init__(self):
        self.ollama_available = self._check_ollama()
        self.piper_available = self._check_piper()

    def _check_ollama(self) -> bool:
        """Verificar si Ollama está disponible."""
        try:
            result = subprocess.run(["ollama", "--version"], capture_output=True, timeout=5)
            return result.returncode == 0
        except Exception:
            return False

    def _check_piper(self) -> bool:
        """Verificar si piper-tts está disponible."""
        try:
            result = subprocess.run(["piper", "--version"], capture_output=True, timeout=5)
            return result.returncode == 0
        except Exception:
            return False

    def transcribe(self, audio_file: str) -> str:
        """
        Transcribir audio a texto usando Whisper vía Ollama.

        Args:
            audio_file: Ruta al archivo de audio

        Returns:
            Texto transcrito
        """
        if not self.ollama_available:
            logger.warning("Ollama no disponible, no se puede transcribir")
            return "[ERROR] Ollama no disponible para transcripción"

        try:
            audio_path = Path(audio_file)
            if not audio_path.exists():
                return f"[ERROR] Archivo no encontrado: {audio_file}"

            # Usar ollama run whisper
            result = subprocess.run(
                ["ollama", "run", "whisper", str(audio_path)],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode == 0:
                return result.stdout.strip()
            else:
                return f"[ERROR] Whisper falló: {result.stderr}"
        except Exception as e:
            logger.error(f"Error en transcripción: {e}")
            return f"[ERROR] {str(e)}"

    def synthesize(self, texto: str, output_file: str) -> str:
        """
        Sintetizar texto a audio usando piper-tts.

        Args:
            texto: Texto a sintetizar
            output_file: Ruta del archivo de audio de salida

        Returns:
            Ruta del archivo generado o mensaje de error
        """
        if not self.piper_available:
            logger.warning("piper-tts no disponible, generando placeholder")
            return f"[PLACEHOLDER] Audio no generado (piper-tts no instalado): {texto[:50]}..."

        try:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Usar piper-tts
            result = subprocess.run(
                ["piper", "--model", "es_ES-x-lowlands.onnx", "--output_file", str(output_path)],
                input=texto,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                return str(output_path)
            else:
                return f"[ERROR] piper-tts falló: {result.stderr}"
        except Exception as e:
            logger.error(f"Error en síntesis: {e}")
            return f"[ERROR] {str(e)}"


if __name__ == "__main__":
    service = VoiceService()
    print(f"Ollama disponible: {service.ollama_available}")
    print(f"Piper disponible: {service.piper_available}")
    print("OK")

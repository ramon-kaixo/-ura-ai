#!/usr/bin/env python3
"""
Whisper Transcriber - Transcribe audio de vídeos usando openai-whisper
"""

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class WhisperTranscriber:
    """Transcribe audio de vídeos usando Whisper (openai-whisper)"""

    def __init__(self, model_size: str = "base"):
        """
        Inicializar transcriptor

        Args:
            model_size: Tamaño del modelo Whisper (tiny, base, small, medium, large)
                        Default: base (buen balance velocidad/precisión)
        """
        self.model_size = model_size
        self._check_whisper()

    def _check_whisper(self) -> bool:
        """Verificar que Whisper está instalado"""
        try:
            pass

            logger.info(f"Whisper detectado (modelo: {self.model_size})")
            return True
        except ImportError:
            logger.warning("openai-whisper no instalado. Intentando instalar...")
            self._install_whisper()
            return False

    def _install_whisper(self) -> None:
        """Instalar openai-whisper automáticamente"""
        try:
            logger.info("Instalando openai-whisper...")
            subprocess.run(["pip", "install", "openai-whisper"], check=True, timeout=300)
            logger.info("openai-whisper instalado correctamente")
        except subprocess.CalledProcessError as e:
            logger.error(f"Error instalando openai-whisper: {e}")
            raise RuntimeError("No se pudo instalar openai-whisper automáticamente")

    def transcribir(
        self, video_path: str | Path, language: str | None = None, task: str = "transcribe"
    ) -> str:
        """
        Transcribe audio de un vídeo

        Args:
            video_path: Ruta al vídeo
            language: Código de idioma (es, en, fr, etc.) o None para auto-detectar
            task: "transcribe" o "translate" (traducir a inglés)

        Returns:
            Texto transcrito completo
        """
        video_path = Path(video_path)

        if not video_path.exists():
            raise FileNotFoundError(f"Vídeo no encontrado: {video_path}")

        logger.info(f"Transcribiendo {video_path} con Whisper ({self.model_size})...")

        try:
            import whisper

            # Cargar modelo
            model = whisper.load_model(self.model_size)

            # Transcribir
            result = model.transcribe(
                str(video_path),
                language=language,
                task=task,
                fp16=False,  # Desactivar FP16 para mejor compatibilidad
            )

            texto = result["text"].strip()
            logger.info(f"Transcripción completada: {len(texto)} caracteres")

            return texto

        except Exception as e:
            logger.error(f"Error transcribiendo: {e}")
            raise

    def transcribir_con_timestamps(
        self, video_path: str | Path, language: str | None = None
    ) -> dict:
        """
        Transcribe con timestamps

        Args:
            video_path: Ruta al vídeo
            language: Código de idioma o None para auto-detectar

        Returns:
            Diccionario con texto y segmentos con timestamps
        """
        video_path = Path(video_path)

        if not video_path.exists():
            raise FileNotFoundError(f"Vídeo no encontrado: {video_path}")

        logger.info(f"Transcribiendo {video_path} con timestamps...")

        try:
            import whisper

            model = whisper.load_model(self.model_size)
            result = model.transcribe(
                str(video_path), language=language, task="transcribe", fp16=False
            )

            segmentos = [
                {"inicio": seg["start"], "fin": seg["end"], "texto": seg["text"].strip()}
                for seg in result["segments"]
            ]

            return {
                "texto_completo": result["text"].strip(),
                "idioma_detectado": result.get("language"),
                "segmentos": segmentos,
                "duracion": result.get("duration", 0),
            }

        except Exception as e:
            logger.error(f"Error transcribiendo con timestamps: {e}")
            raise

    def traducir_a_ingles(self, video_path: str | Path) -> str:
        """
        Traduce audio de un vídeo al inglés

        Args:
            video_path: Ruta al vídeo

        Returns:
            Texto traducido al inglés
        """
        return self.transcribir(video_path, task="translate")


if __name__ == "__main__":
    # Test whisper transcriber
    transcriptor = WhisperTranscriber(model_size="base")

    # Test con un vídeo de ejemplo si existe
    test_video = Path("/tmp/test_video.mp4")
    if test_video.exists():
        texto = transcriptor.transcribir(test_video, language="es")
        print(f"Transcripción:\n{texto}")

        # Test con timestamps
        resultado = transcriptor.transcribir_con_timestamps(test_video, language="es")
        print(f"\nSegmentos: {len(resultado['segmentos'])}")
        for seg in resultado["segmentos"][:3]:
            print(f"[{seg['inicio']:.2f}s - {seg['fin']:.2f}s] {seg['texto']}")
    else:
        print("No hay vídeo de prueba. Crea uno en /tmp/test_video.mp4")

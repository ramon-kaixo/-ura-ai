#!/usr/bin/env python3
"""
Frame Extractor - Extrae frames de vídeos usando FFmpeg
"""

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class FrameExtractor:
    """Extrae frames de vídeos usando FFmpeg"""

    def __init__(self):
        """Inicializar extractor"""
        self._check_ffmpeg()

    def _check_ffmpeg(self) -> bool:
        """Verificar que FFmpeg está instalado"""
        try:
            subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True, timeout=5)
            logger.info("FFmpeg detectado correctamente")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.error(
                "FFmpeg no está instalado. Instala con: brew install ffmpeg (macOS) o apt install ffmpeg (Linux)"
            )
            return False

    def extraer_frames(
        self, video_path: str | Path, output_dir: str | Path, intervalo: int = 2
    ) -> list[Path]:
        """
        Extrae frames de un vídeo cada X segundos

        Args:
            video_path: Ruta al vídeo de entrada
            output_dir: Directorio de salida para los frames
            intervalo: Intervalo en segundos entre frames (default: 2)

        Returns:
            Lista de rutas a los frames extraídos
        """
        video_path = Path(video_path)
        output_dir = Path(output_dir)

        if not video_path.exists():
            raise FileNotFoundError(f"Vídeo no encontrado: {video_path}")

        output_dir.mkdir(parents=True, exist_ok=True)

        # Usar FFmpeg para extraer frames
        # -vf fps=1/2 = 1 frame cada 2 segundos
        # frame_%03d.png = frame_001.png, frame_002.png, etc.
        cmd = [
            "ffmpeg",
            "-i",
            str(video_path),
            "-vf",
            f"fps=1/{intervalo}",
            str(output_dir / "frame_%03d.png"),
            "-y",  # Sobrescribir archivos existentes
        ]

        logger.info(f"Extrayendo frames de {video_path} cada {intervalo} segundos...")

        try:
            subprocess.run(
                cmd,
                capture_output=True,
                check=True,
                timeout=3600,  # 1 hora máximo
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"Error extrayendo frames: {e.stderr.decode()}")
            raise
        except subprocess.TimeoutExpired:
            logger.error("Timeout extrayendo frames")
            raise
        except FileNotFoundError:
            logger.error("FFmpeg no encontrado")
            raise RuntimeError("FFmpeg no está instalado")

        # Listar frames extraídos
        frames = sorted(output_dir.glob("frame_*.png"))
        logger.info(f"Frames extraídos: {len(frames)}")

        return frames

    def extraer_frame_unico(
        self, video_path: str | Path, timestamp: float, output_path: str | Path
    ) -> Path:
        """
        Extrae un frame específico en un timestamp

        Args:
            video_path: Ruta al vídeo
            timestamp: Timestamp en segundos
            output_path: Ruta de salida del frame

        Returns:
            Ruta al frame extraído
        """
        video_path = Path(video_path)
        output_path = Path(output_path)

        output_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            "ffmpeg",
            "-ss",
            str(timestamp),
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            str(output_path),
            "-y",
        ]

        logger.info(f"Extrayendo frame en {timestamp}s de {video_path}...")

        try:
            subprocess.run(cmd, capture_output=True, check=True, timeout=60)
        except subprocess.CalledProcessError as e:
            logger.error(f"Error extrayendo frame: {e.stderr.decode()}")
            raise

        logger.info(f"Frame extraído: {output_path}")
        return output_path

    def obtener_duracion(self, video_path: str | Path) -> float:
        """
        Obtiene la duración de un vídeo en segundos

        Args:
            video_path: Ruta al vídeo

        Returns:
            Duración en segundos
        """
        video_path = Path(video_path)

        if not video_path.exists():
            raise FileNotFoundError(f"Vídeo no encontrado: {video_path}")

        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, check=True, timeout=30)
            duracion = float(result.stdout.strip())
            logger.info(f"Duración de {video_path}: {duracion}s")
            return duracion
        except subprocess.CalledProcessError as e:
            logger.error(f"Error obteniendo duración: {e.stderr.decode()}")
            raise


if __name__ == "__main__":
    # Test frame extractor
    extractor = FrameExtractor()

    # Test con un vídeo de ejemplo si existe
    test_video = Path("/tmp/test_video.mp4")
    if test_video.exists():
        frames = extractor.extraer_frames(test_video, "/tmp/frames_output", intervalo=2)
        print(f"Frames extraídos: {len(frames)}")
    else:
        print("No hay vídeo de prueba. Crea uno en /tmp/test_video.mp4")

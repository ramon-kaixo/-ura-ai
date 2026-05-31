#!/usr/bin/env python3
"""
agente_video.py — Agente de vídeo para URA
Orquesta extracción de frames, transcripción de audio, análisis de visión e indexación vectorial
"""

import logging
from datetime import datetime
from pathlib import Path

# Importar componentes del sistema
import sys

SISTEMA = Path(__file__).parent.parent
sys.path.insert(0, str(SISTEMA))

from core.frame_extractor import FrameExtractor
from core.whisper_transcriber import WhisperTranscriber
from core.vector_database import get_vector_store
from core.embedding_service import get_embedding_service
from agents.agente_vision import AgenteVision
from agents.agente_memoria import get_memoria

logger = logging.getLogger(__name__)


class AgenteVideo:
    """Agente de vídeo para URA que orquesta análisis completo de vídeos"""

    def __init__(self, persist_directory: str | Path = None):
        """
        Inicializar agente de vídeo

        Args:
            persist_directory: Directorio para persistir datos vectoriales
        """
        self.frame_extractor = FrameExtractor()
        self.whisper_transcriber = WhisperTranscriber(model_size="base")
        self.agente_vision = AgenteVision()
        self.vector_store = get_vector_store(persist_directory=persist_directory)
        self.embedding_service = get_embedding_service()
        self.memoria = get_memoria()


def execute(self, video_path: str | Path, intervalo_frames: int = 2) -> dict:
    """
    Orquesta análisis completo de un vídeo

    Args:
        video_path: Ruta al vídeo
        intervalo_frames: Intervalo en segundos entre frames (default: 2)

    Returns:
        Diccionario con resultados del análisis
    """
    video_path = Path(video_path)

    if not video_path.exists():
        raise FileNotFoundError(f"Vídeo no encontrado: {video_path}")

    logger.info(f"Iniciando análisis de vídeo: {video_path}")
    video_id = video_path.stem
    output_dir = video_path.parent / f"{video_id}_frames"

    resultado = {
        "video_id": video_id,
        "video_path": str(video_path),
        "inicio": datetime.now().isoformat(),
        "frames_extraidos": 0,
        "transcripcion": None,
        "frames_analizados": 0,
        "errores": [],
    }

    try:
        resultado = extraer_frames(self, video_path, output_dir, intervalo_frames, resultado)
        resultado = transcribir_audio(self, video_path, resultado)
        resultado = analizar_frames_vision(
            self, frames=resultado["frames_extraidos"], resultado=resultado
        )
        guardar_referencia_en_memoria(self, video_id, resultado)

        return resultado

    except Exception as e:
        logger.error(f"Error en análisis de vídeo: {e}")
        resultado["estado"] = "error"
        resultado["errores"].append(str(e))
        resultado["fin"] = datetime.now().isoformat()
        return resultado


def extraer_frames(
    self, video_path: Path, output_dir: Path, intervalo_frames: int, resultado: dict
) -> dict:
    logger.info("Extrayendo frames...")
    frames = self.frame_extractor.extraer_frames(video_path, output_dir, intervalo=intervalo_frames)
    resultado["frames_extraidos"] = len(frames)
    logger.info(f"Frames extraídos: {len(frames)}")
    return resultado


def transcribir_audio(self, video_path: Path, resultado: dict) -> dict:
    logger.info("Transcribiendo audio...")
    try:
        transcripcion = self.whisper_transcriber.transcribir(video_path, language="es")
        resultado["transcripcion"] = transcripcion
        logger.info(f"Transcripción completada: {len(transcripcion)} caracteres")

        # Indexar transcripción en VectorStore
        embedding_transcripcion = self.embedding_service.encode(transcripcion)
        self.vector_store.agregar_documento(
            texto=transcripcion,
            metadatos={
                "tipo": "transcripcion_audio",
                "video_id": resultado["video_id"],
                "video_path": str(video_path),
            },
            embedding=embedding_transcripcion,
        )
    except Exception as e:
        logger.error(f"Error transcribiendo audio: {e}")
        resultado["errores"].append(f"Transcripción fallida: {e}")

    return resultado


def analizar_frames_vision(self, frames: int, resultado: dict) -> dict:
    logger.info("Analizando frames con visión...")
    for i in range(frames):
        try:
            frame_path = self.frame_extractor.get_frame_path(i)
            descripcion = self.agente_vision.execute(frame_path)

            if descripcion:
                # Obtener timestamp del frame
                timestamp = i * resultado["intervalo_frames"]

                # Indexar frame en VectorStore
                embedding_frame = self.embedding_service.encode(descripcion)
                self.vector_store.agregar_frame(
                    frame_path=frame_path,
                    descripcion=descripcion,
                    embedding=embedding_frame,
                    video_id=resultado["video_id"],
                    timestamp=timestamp,
                )

                resultado["frames_analizados"] += 1

                if i % 5 == 0:  # Log cada 5 frames
                    logger.info(f"Frames analizados: {i + 1}/{frames}")
        except Exception as e:
            logger.error(f"Error analizando frame {frame_path}: {e}")
            resultado["errores"].append(f"Frame {frame_path.name}: {e}")

    return resultado


def guardar_referencia_en_memoria(self, video_id: str, resultado: dict):
    logger.info("Guardando referencia en memoria...")
    _guardar_contenido_en_memoria(
        contenido=f"Vídeo analizado: {video_id} con {resultado['frames_extraidos']} frames y transcripción de {len(resultado['transcripcion']) if resultado['transcripcion'] else 0} caracteres",
        tipo="video",
        importancia=8,
    )


def _guardar_contenido_en_memoria(contenido: str, tipo: str, importancia: int):
    self.memoria.recordar(contenido=contenido, tipo=tipo, importancia=importancia)


# Singleton para consistencia con otros agentes
_video_instance = None


def get_agente_video(persist_directory: str | Path = None) -> AgenteVideo:
    """Obtener instancia singleton de AgenteVideo"""
    global _video_instance
    if _video_instance is None:
        _video_instance = AgenteVideo(persist_directory=persist_directory)
    return _video_instance


if __name__ == "__main__":
    import json

    # Configurar logging
    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 2:
        print("Uso: python agente_video.py <comando> [argumentos]")
        print("Comandos:")
        print("  analizar <video_path> - Analizar un vídeo completo")
        print("  buscar <consulta> - Buscar en vídeos indexados")
        print("  buscar-frame <imagen_path> - Buscar frames similares a una imagen")
        sys.exit(1)

    comando = sys.argv[1]

    if comando == "analizar":
        if len(sys.argv) < 3:
            print("Error: se requiere ruta del vídeo")
            sys.exit(1)

        video_path = sys.argv[2]
        agente = AgenteVideo()
        resultado = agente.execute(video_path)
        print(json.dumps(resultado, indent=2, ensure_ascii=False))

    elif comando == "buscar":
        if len(sys.argv) < 3:
            print("Error: se requiere consulta de búsqueda")
            sys.exit(1)

        consulta = " ".join(sys.argv[2:])
        agente = AgenteVideo()
        resultado = agente.buscar_en_video(consulta)
        print(json.dumps(resultado, indent=2, ensure_ascii=False))

    elif comando == "buscar-frame":
        if len(sys.argv) < 3:
            print("Error: se requiere ruta de la imagen de referencia")
            sys.exit(1)

        imagen_path = sys.argv[2]
        agente = AgenteVideo()
        resultado = agente.buscar_similar_frames(imagen_path)
        print(json.dumps(resultado, indent=2, ensure_ascii=False))

    else:
        print(f"Comando desconocido: {comando}")
        sys.exit(1)

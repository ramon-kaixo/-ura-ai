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
            # 1. Extraer frames
            logger.info("Extrayendo frames...")
            frames = self.frame_extractor.extraer_frames(
                video_path, output_dir, intervalo=intervalo_frames
            )
            resultado["frames_extraidos"] = len(frames)
            logger.info(f"Frames extraídos: {len(frames)}")

            # 2. Transcribir audio
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
                        "video_id": video_id,
                        "video_path": str(video_path),
                    },
                    embedding=embedding_transcripcion,
                )
            except Exception as e:
                logger.error(f"Error transcribiendo audio: {e}")
                resultado["errores"].append(f"Transcripción fallida: {e}")

            # 3. Analizar cada frame con visión
            logger.info("Analizando frames con visión...")
            for i, frame_path in enumerate(frames):
                try:
                    descripcion = self.agente_vision.execute(frame_path)

                    if descripcion:
                        # Obtener timestamp del frame
                        timestamp = i * intervalo_frames

                        # Indexar frame en VectorStore
                        embedding_frame = self.embedding_service.encode(descripcion)
                        self.vector_store.agregar_frame(
                            frame_path=frame_path,
                            descripcion=descripcion,
                            embedding=embedding_frame,
                            video_id=video_id,
                            timestamp=timestamp,
                        )

                        resultado["frames_analizados"] += 1

                        if i % 5 == 0:  # Log cada 5 frames
                            logger.info(f"Frames analizados: {i + 1}/{len(frames)}")
                except Exception as e:
                    logger.error(f"Error analizando frame {frame_path}: {e}")
                    resultado["errores"].append(f"Frame {frame_path.name}: {e}")

            # 4. Guardar referencia en memoria
            logger.info("Guardando referencia en memoria...")
            self.memoria.recordar(
                contenido=f"Vídeo analizado: {video_id} con {resultado['frames_extraidos']} frames y transcripción de {len(resultado['transcripcion']) if resultado['transcripcion'] else 0} caracteres",
                tipo="video",
                importancia=8,
            )

            resultado["fin"] = datetime.now().isoformat()
            resultado["estado"] = "completado"

            logger.info(f"Análisis completado: {resultado['estado']}")
            return resultado

        except Exception as e:
            logger.error(f"Error en análisis de vídeo: {e}")
            resultado["estado"] = "error"
            resultado["errores"].append(str(e))
            resultado["fin"] = datetime.now().isoformat()
            return resultado

    def buscar_en_video(self, consulta: str, video_id: str = None, top_k: int = 5) -> dict:
        """
        Busca en los vectores indexados de un vídeo

        Args:
            consulta: Consulta de búsqueda
            video_id: Filtrar por ID de vídeo (opcional)
            top_k: Número de resultados (default: 5)

        Returns:
            Diccionario con resultados de búsqueda
        """
        logger.info(f"Buscando: '{consulta}' en vídeo {video_id or 'todos'}")

        # Generar embedding de la consulta
        embedding_consulta = self.embedding_service.encode(consulta)

        # Buscar en documentos (transcripciones)
        resultados_docs = self.vector_store.buscar_similares(
            embedding=embedding_consulta, top_k=top_k
        )

        # Buscar en frames
        resultados_frames = self.vector_store.buscar_frames(
            embedding=embedding_consulta, video_id=video_id, top_k=top_k
        )

        return {
            "consulta": consulta,
            "video_id": video_id,
            "resultados_documentos": resultados_docs,
            "resultados_frames": resultados_frames,
            "total_documentos": len(resultados_docs),
            "total_frames": len(resultados_frames),
        }

    def buscar_similar_frames(
        self, imagen_path: str | Path, video_id: str = None, top_k: int = 5
    ) -> dict:
        """
        Busca frames similares a una imagen de referencia

        Args:
            imagen_path: Ruta a la imagen de referencia
            video_id: Filtrar por ID de vídeo (opcional)
            top_k: Número de resultados (default: 5)

        Returns:
            Diccionario con frames similares
        """
        imagen_path = Path(imagen_path)

        if not imagen_path.exists():
            raise FileNotFoundError(f"Imagen no encontrada: {imagen_path}")

        logger.info(f"Buscando frames similares a: {imagen_path}")

        # Analizar imagen de referencia
        descripcion_ref = self.agente_vision.execute(imagen_path)

        if not descripcion_ref:
            return {"error": "No se pudo analizar la imagen de referencia"}

        # Generar embedding de la descripción
        embedding_ref = self.embedding_service.encode(descripcion_ref)

        # Buscar frames similares
        resultados = self.vector_store.buscar_frames(
            embedding=embedding_ref, video_id=video_id, top_k=top_k
        )

        return {
            "imagen_referencia": str(imagen_path),
            "descripcion_referencia": descripcion_ref,
            "video_id": video_id,
            "resultados": resultados,
            "total": len(resultados),
        }

    # Métodos de compatibilidad con interfaz de agentes URA
    def procesar(self, texto: str) -> str:
        """Procesar consulta para AgenteVideo"""
        texto_lower = texto.lower()

        if "analizar" in texto_lower or "procesar" in texto_lower:
            # Extraer ruta del vídeo del texto
            palabras = texto.split()
            for palabra in palabras:
                if palabra.endswith((".mp4", ".mov", ".avi", ".mkv")):
                    try:
                        resultado = self.execute(palabra)
                        return f"Vídeo analizado: {resultado['frames_extraidos']} frames, {len(resultado['transcripcion']) if resultado['transcripcion'] else 0} caracteres de transcripción. Errores: {len(resultado['errores'])}"
                    except Exception as e:
                        return f"Error analizando vídeo: {e}"
            return "Por favor proporciona la ruta del vídeo (ej: .mp4, .mov, .avi, .mkv)"

        elif "buscar" in texto_lower:
            # Buscar en vídeos indexados
            palabras = texto.split()
            consulta = " ".join([p for p in palabras if p.lower() != "buscar"])
            if consulta:
                resultados = self.buscar_en_video(consulta)
                return f"Encontrados {resultados['total_documentos']} documentos y {resultados['total_frames']} frames para '{consulta}'"
            return "Por favor proporciona una consulta de búsqueda"

        else:
            return "Puedo analizar vídeos (extraer frames, transcribir audio, analizar visión) y buscar en contenido indexado. Usa: analizar [vídeo] o buscar [consulta]"

    def ejecutar(self, texto: str) -> str:
        """Ejecutar acción para AgenteVideo"""
        return self.procesar(texto)

    def consultar(self, texto: str) -> str:
        """Consultar información para AgenteVideo"""
        return self.procesar(texto)

    def responder(self, texto: str) -> str:
        """Responder pregunta para AgenteVideo"""
        return self.procesar(texto)


# Singleton para consistencia con otros agentes
_video_instance = None


def get_agente_video(persist_directory: str | Path = None) -> AgenteVideo:
    """Obtener instancia singleton de AgenteVideo"""
    global _video_instance
    if _video_instance is None:
        _video_instance = AgenteVideo(persist_directory=persist_directory)
    return _video_instance


if __name__ == "__main__":
    import sys
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

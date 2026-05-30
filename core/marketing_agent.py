#!/usr/bin/env python3
"""
Agente de Marketing - Fase 4
Creación de banners, videos, programación de publicaciones.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

KNOWLEDGE_PATH = Path(__file__).parent / "marketing_templates.json"

try:
    from PIL import Image, ImageDraw, ImageFont

    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False
    logger.warning("Pillow no disponible, usando placeholders")


class MarketingAgent:
    """Agente de marketing para crear contenido visual."""

    def __init__(self, knowledge_path: Path = None):
        if knowledge_path is None:
            knowledge_path = KNOWLEDGE_PATH
        self.knowledge_path = knowledge_path
        self.knowledge = self._load_knowledge()

    def _load_knowledge(self) -> dict:
        """Cargar plantillas de marketing."""
        if self.knowledge_path.exists():
            try:
                with open(self.knowledge_path, encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Error cargando plantillas: {e}")
        return self._default_knowledge()

    def _default_knowledge(self) -> dict:
        """Plantillas por defecto."""
        return {
            "colores": {
                "gradiente_azul": ["#00f2fe", "#4facfe"],
                "gradiente_rojo": ["#ff6b6b", "#ff8e53"],
                "gradiente_verde": ["#00e676", "#00c853"],
            },
            "tamanos": {"twitter": [1200, 675], "instagram": [1080, 1080], "facebook": [1200, 630]},
        }

    def crear_banner(self, texto: str, colores: list = None, tamano: list = None) -> str:
        """Crear banner (ruta imagen o placeholder)."""
        if not PILLOW_AVAILABLE:
            return f"[PLACEHOLDER] Banner: {texto} (Pillow no instalado)"

        try:
            if colores is None:
                colores = self.knowledge["colores"]["gradiente_azul"]
            if tamano is None:
                tamano = self.knowledge["tamanos"]["twitter"]

            img = Image.new("RGB", tuple(tamano), colores[0])
            draw = ImageDraw.Draw(img)

            # Texto centrado
            try:
                font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 40)
            except:
                font = ImageFont.load_default()

            bbox = draw.textbbox((0, 0), texto, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            x = (tamano[0] - text_width) // 2
            y = (tamano[1] - text_height) // 2

            draw.text((x, y), texto, fill="white", font=font)

            output_path = Path(__file__).parent / f"banner_{hash(texto)}.png"
            img.save(output_path)
            return str(output_path)
        except Exception as e:
            logger.error(f"Error creando banner: {e}")
            return f"[ERROR] No se pudo crear banner: {e}"

    def crear_video_promocional(self, texto: str, duracion: int = 10) -> str:
        """Crear video promocional (placeholder)."""
        return f"[PLACEHOLDER] Video: {texto} ({duracion}s) - MoviePy no integrado"

    def programar_publicacion(self, red: str, contenido: str, fecha: str) -> dict:
        """Programar publicación (simulado)."""
        return {"red": red, "contenido": contenido, "fecha": fecha, "estado": "programado"}

    def obtener_metricas(self, red: str, periodo: str = "7d") -> dict:
        """Obtener métricas (simulado)."""
        return {"red": red, "periodo": periodo, "impresiones": 1000, "clics": 50, "ctr": 0.05}


if __name__ == "__main__":
    agent = MarketingAgent()
    print("Banner:", agent.crear_banner("Oferta especial"))
    print("Video:", agent.crear_video_promocional("Promo verano"))

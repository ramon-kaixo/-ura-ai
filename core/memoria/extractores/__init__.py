from pathlib import Path
from typing import Any

from core.memoria.extractores.html_extractor import extraer_html
from core.memoria.extractores.imagen_extractor import extraer_imagen
from core.memoria.extractores.media_extractor import extraer_audio, extraer_video
from core.memoria.extractores.office_extractor import extraer_office
from core.memoria.extractores.pdf_extractor import extraer_pdf
from core.memoria.extractores.video_pipeline import pipeline_video

EXTRACTORES: dict[str, Any] = {
    "html": extraer_html,
    "pdf": extraer_pdf,
    "imagen": extraer_imagen,
    "video": extraer_video,
    "audio": extraer_audio,
    "office": extraer_office,
    "texto": extraer_html,  # texto simple se trata como HTML
}


def extraer_archivo(ruta: Path, tipo: str) -> dict | None:
    extractor = EXTRACTORES.get(tipo)
    if not extractor:
        return None
    try:
        return extractor(ruta)
    except Exception as e:
        return {"tipo": tipo, "error": str(e), "ruta": str(ruta)}


__all__ = ["EXTRACTORES", "extraer_archivo"]


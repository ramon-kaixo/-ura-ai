from pathlib import Path
from typing import Any

from core.memoria.extractores.html_extractor import extraer_html
from core.memoria.extractores.pdf_extractor import extraer_pdf

EXTRACTORES: dict[str, Any] = {
    "html": extraer_html,
    "pdf": extraer_pdf,
}


def extraer_archivo(ruta: Path, tipo: str) -> dict | None:
    extractor = EXTRACTORES.get(tipo)
    if not extractor:
        return None
    try:
        return extractor(ruta)
    except Exception as e:
        return {"tipo": tipo, "error": str(e), "ruta": str(ruta)}


__all__ = ["extraer_archivo", "EXTRACTORES"]

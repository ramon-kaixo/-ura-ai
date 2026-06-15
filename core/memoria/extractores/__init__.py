"""Extractores de contenido para archivos."""
import json
from pathlib import Path


def extraer_archivo(ruta: str, tipo: str = "texto") -> dict:
    """Extrae texto plano de un archivo según su tipo."""
    p = Path(ruta)
    if not p.exists():
        return {"texto_plano": "", "error": "no existe"}
    try:
        if tipo == "imagen" or p.suffix.lower() in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
            from core.memoria.extractores.imagen_extractor import _exif_pillow
            meta = _exif_pillow(p)
            return {"texto_plano": json.dumps(meta, default=str), "metadatos": meta}
        texto = p.read_text(encoding="utf-8", errors="replace")
        return {"texto_plano": texto[:100000]}
    except Exception as e:
        return {"texto_plano": "", "error": str(e)}

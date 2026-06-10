import json
import os
from datetime import datetime
from pathlib import Path

from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS


def _extraer_exif(ruta: Path) -> dict:
    resultado: dict = {"fecha": "", "camara": "", "gps": None, "exif_raw": {}}
    try:
        img = Image.open(ruta)
        exif_data = img._getexif()
        if not exif_data:
            return resultado

        for tag_id, valor in exif_data.items():
            tag_name = TAGS.get(tag_id, tag_id)
            if isinstance(valor, bytes):
                valor = valor.decode(errors="replace")[:200]
            elif isinstance(valor, (int, float, str)):
                pass
            else:
                valor = str(valor)[:200]
            resultado["exif_raw"][str(tag_name)] = valor

            if tag_name == "DateTimeOriginal" or tag_name == "DateTime":
                resultado["fecha"] = str(valor)
            elif tag_name == "Make":
                resultado["camara"] = f"{valor} {resultado['camara']}".strip()
            elif tag_name == "Model":
                resultado["camara"] = f"{resultado['camara']} {valor}".strip()
            elif tag_name == "GPSInfo":
                gps = {}
                for gps_tag_id, gps_valor in valor.items():
                    gps_tag_name = GPSTAGS.get(gps_tag_id, str(gps_tag_id))
                    gps[gps_tag_name] = str(gps_valor)[:100]
                if "GPSLatitude" in gps and "GPSLongitude" in gps:
                    resultado["gps"] = f"{gps.get('GPSLatitude','')}, {gps.get('GPSLongitude','')}"
                elif "GPSLatitude" in gps:
                    resultado["gps"] = str(gps.get("GPSLatitude", ""))
    except Exception:
        pass
    return resultado


def extraer_imagen(ruta: Path) -> dict:
    img = Image.open(ruta)
    exif = _extraer_exif(ruta)

    return {
        "tipo": "imagen",
        "metadatos": {
            "formato": img.format or "desconocido",
            "dimensiones": f"{img.width}x{img.height}",
            "modo": img.mode,
            "fecha": exif.get("fecha", ""),
            "camara": exif.get("camara", ""),
            "gps": exif.get("gps"),
            "tamano_bytes": ruta.stat().st_size,
        },
        "texto_plano": "",  # imágenes no generan texto (se hará con OCR en fase posterior)
        "ruta": str(ruta),
    }

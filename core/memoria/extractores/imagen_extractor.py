import json
import subprocess
from pathlib import Path

from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS


def _exif_pillow(ruta: Path) -> dict:
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


def _exif_exiftool(ruta: Path) -> dict:
    resultado: dict = {"fecha": "", "camara": "", "gps": None, "exif_raw": {}}
    try:
        out = subprocess.run(
            ["exiftool", "-json", "-DateTimeOriginal", "-Make", "-Model",
             "-GPSLatitude", "-GPSLongitude", "-ImageWidth", "-ImageHeight",
             "-IPTCDigest", "-ObjectName", str(ruta)],
            capture_output=True, text=True, timeout=10,
        )
        if out.returncode != 0 or not out.stdout.strip():
            return resultado
        data = json.loads(out.stdout)
        item = data[0] if data else {}
        resultado["fecha"] = item.get("DateTimeOriginal", "")
        make = item.get("Make", "")
        model = item.get("Model", "")
        if make or model:
            resultado["camara"] = f"{make} {model}".strip()
        lat = item.get("GPSLatitude", "")
        lon = item.get("GPSLongitude", "")
        if lat and lon:
            resultado["gps"] = f"{lat}, {lon}"
        elif lat:
            resultado["gps"] = str(lat)
        resultado["exif_raw"] = {k: v for k, v in item.items() if k not in ("SourceFile",)}
    except Exception:
        pass
    return resultado


def extraer_imagen(ruta: Path) -> dict:
    img = Image.open(ruta)

    exif = _exif_pillow(ruta)
    if not exif.get("fecha") and not exif.get("camara"):
        exiftool_data = _exif_exiftool(ruta)
        if exiftool_data.get("fecha"):
            exif["fecha"] = exif["fecha"] or exiftool_data["fecha"]
        if exiftool_data.get("camara"):
            exif["camara"] = exif["camara"] or exiftool_data["camara"]
        if exiftool_data.get("gps"):
            exif["gps"] = exif["gps"] or exiftool_data["gps"]
        if exiftool_data.get("exif_raw"):
            exif["exif_raw"] = {**exif["exif_raw"], **exiftool_data["exif_raw"]}

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
        "texto_plano": "",
        "ruta": str(ruta),
    }

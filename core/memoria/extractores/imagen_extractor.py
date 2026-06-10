import json
import subprocess
from pathlib import Path

import httpx
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

OLLAMA = "http://127.0.0.1:11434/api/chat"
VISION_MODEL = "llama3.2-vision:11b"


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

            if tag_name in ("DateTimeOriginal", "DateTime"):
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
             "-GPSLatitude", "-GPSLongitude", "-ImageWidth", "-ImageHeight", str(ruta)],
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
        resultado["exif_raw"] = {k: v for k, v in item.items() if k != "SourceFile"}
    except Exception:
        pass
    return resultado


def _paleta_colores(ruta: Path, k: int = 5) -> list[str]:
    try:
        img = Image.open(ruta).convert("RGB")
        img = img.resize((100, 100))
        import numpy as np
        from collections import Counter
        pixels = np.array(img).reshape(-1, 3)
        counter = Counter(map(tuple, pixels))
        return [f"#{r:02x}{g:02x}{b:02x}" for (r, g, b), _ in counter.most_common(k)]
    except Exception:
        return []


def _describir_imagen(ruta: Path) -> dict:
    try:
        import base64
        img_b64 = base64.b64encode(ruta.read_bytes()).decode()
        resp = httpx.post(OLLAMA, json={
            "model": VISION_MODEL,
            "messages": [{
                "role": "user",
                "content": "Describe esta imagen en espanol en 2 frases: que muestra, colores, estilo y atmosfera.",
                "images": [img_b64],
            }],
            "stream": False,
            "options": {"temperature": 0.0, "num_predict": 200},
        }, timeout=60)
        if resp.is_error:
            return {"descripcion": "", "error": f"Ollama {resp.status_code}"}
        data = resp.json()
        desc = data.get("message", {}).get("content", "").strip()
        return {"descripcion": desc, "modelo": VISION_MODEL}
    except Exception as e:
        return {"descripcion": "", "error": str(e)}


def _extraer_iptc(ruta: Path) -> dict:
    """Extrae metadatos IPTC via iptcinfo3 usando record numbers."""
    try:
        from iptcinfo3 import IPTCInfo
        info = IPTCInfo(str(ruta))
        data = info._data if hasattr(info, '_data') else {}

        def _bytes(val):
            return val.decode() if isinstance(val, bytes) else str(val) if val else ""

        keywords = data.get(25, []) or []
        return {
            "titulo": _bytes(data.get(5, b"")),
            "descripcion": _bytes(data.get(120, b"")),
            "autor": _bytes(data.get(80, b"")),
            "keywords": [k.decode() if isinstance(k, bytes) else str(k) for k in keywords],
            "ciudad": _bytes(data.get(90, b"")),
            "pais": _bytes(data.get(101, b"")),
            "copyright": _bytes(data.get(116, b"")),
        }
    except Exception:
        return {}

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

    iptc = _extraer_iptc(ruta)
    vis = _describir_imagen(ruta)
    pal = _paleta_colores(ruta)

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
        "iptc": iptc,
        "resumen_visual": vis.get("descripcion", ""),
        "paleta": pal,
        "texto_plano": "",
        "ruta": str(ruta),
    }

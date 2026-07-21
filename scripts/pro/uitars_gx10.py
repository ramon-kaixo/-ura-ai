#!/usr/bin/env python3
"""uitars_gx10.py — UI-TARS para GX10 con fallback Ollama vision."""

from __future__ import annotations

import base64
import json
import logging
import os
import shutil
import subprocess
import time
import urllib.request
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_PIXEL_AREA = 1280 * 720  # 720p máximo

REPORTS_DIR = Path("/home/ramon/URA/reports")
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def tiene_display() -> bool:
    return bool(os.environ.get("DISPLAY"))


def iniciar_xvfb() -> bool:
    if not shutil.which("Xvfb"):
        return False
    try:
        subprocess.run(["Xvfb", ":99", "-screen", "0", "1280x720x24"], capture_output=True, timeout=5)  # noqa: PLW1510
        os.environ["DISPLAY"] = ":99"
        time.sleep(1)
        return True
    except Exception:
        logger.exception("Failed to start Xvfb")
        return False


def capturar_pantalla() -> str | None:
    try:
        import mss
        from PIL import Image

        with mss.mss() as sct:
            img = sct.grab(sct.monitors[1])
            pil_img = Image.frombytes("RGB", img.size, img.rgb)
            if pil_img.width * pil_img.height > MAX_PIXEL_AREA:
                ratio = (MAX_PIXEL_AREA / (pil_img.width * pil_img.height)) ** 0.5
                pil_img = pil_img.resize((int(pil_img.width * ratio), int(pil_img.height * ratio)))
            buf = BytesIO()
            pil_img.save(buf, format="JPEG", quality=50)
            return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return None


from dataclasses import dataclass


@dataclass
class RespuestaOllama:
    texto: str
    modelo: str = "llama3.2-vision:11b"
    confianza: float = 0.0


def analizar_con_ollama(imagen_b64: str | None, prompt: str) -> RespuestaOllama:
    data = {"model": "llama3.2-vision:11b", "prompt": prompt, "stream": False}
    if imagen_b64:
        data["images"] = [imagen_b64]
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:11434/api/generate",
            data=json.dumps(data).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=120) as r:  # noqa: S310
            resp = json.loads(r.read())
        texto = resp.get("response", "")
        return RespuestaOllama(texto=texto, modelo="llama3.2-vision:11b")
    except Exception as e:
        return RespuestaOllama(texto=f"Error: {e}")


def main() -> None:
    modo = "headless"
    if tiene_display():
        modo = "display"
    elif iniciar_xvfb():
        modo = "xvfb"
    imagen = capturar_pantalla() if modo != "headless" else None
    if imagen:
        pass
    resultado = analizar_con_ollama(imagen, "Describe esta interfaz en detalle")
    path = REPORTS_DIR / f"uitars_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(json.dumps({"modo": modo, "resultado": resultado.texto}, indent=2))


if __name__ == "__main__":
    main()

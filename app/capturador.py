#!/usr/bin/env python3
"""app/capturador.py — Puente a scripts/pro/uitars_gx10.py.
Proporciona CapturadorPantallaSeguro con normalizacion Retina.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.pro.uitars_gx10 import (
    capturar_pantalla, analizar_con_ollama, tiene_display
)

class CapturadorPantallaSeguro:
    """Wrapper con normalizacion Retina para Mac."""
    def __init__(self, normalizar_retina: bool = True) -> None:
        self.normalizar_retina = normalizar_retina
        self.es_mac = sys.platform == "darwin"

    def capturar(self) -> str | None:
        import base64
        b64 = capturar_pantalla()
        if b64 and self.es_mac and self.normalizar_retina:
            from PIL import Image
            from io import BytesIO
            img = Image.open(BytesIO(base64.b64decode(b64)))
            w, h = img.size
            img = img.resize((w // 2, h // 2))
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=50)
            return base64.b64encode(buf.getvalue()).decode()
        return b64

    def analizar(self, imagen_b64: str | None = None, prompt: str = "") -> str:
        r = analizar_con_ollama(imagen_b64, prompt)
        return r.texto if hasattr(r, "texto") else str(r)

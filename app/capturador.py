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
        from PIL import Image
        from io import BytesIO
        b64 = capturar_pantalla()
        if not b64:
            return None
        img = Image.open(BytesIO(base64.b64decode(b64)))
        w, h = img.size
        if self.es_mac and self.normalizar_retina and (w > 1920 or h > 1080):
            img = img.resize((w // 2, h // 2))
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=50)
            return base64.b64encode(buf.getvalue()).decode()
        return b64

    def normalizar_coordenadas(self, x: int, y: int) -> tuple[int, int]:
        """Convierte coordenadas de pantalla Mac Retina a coordenadas reales."""
        if self.es_mac and self.normalizar_retina:
            return x // 2, y // 2
        return x, y

    def analizar(self, imagen_b64: str | None = None, prompt: str = "") -> str:
        r = analizar_con_ollama(imagen_b64, prompt)
        return r.texto if hasattr(r, "texto") else str(r)

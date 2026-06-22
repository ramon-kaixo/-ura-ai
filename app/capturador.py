#!/usr/bin/env python3
"""app/capturador.py — Captura aislada por nodo (ASUS/HETZNER/MAC).
Cada maquina captura su propia pantalla. Sin cruce de contextos.
"""
from __future__ import annotations
import os
import sys

# Identificacion del nodo via variable de entorno (default: ASUS_GX10)
NODO = os.getenv("URA_NODE_ENV", "ASUS_GX10")

class CapturadorTarget:
    """Capturador aislado por nodo. Cada maquina solo ve su pantalla."""

    def __init__(self) -> None:
        self.nodo = NODO
        self.es_mac = sys.platform == "darwin"

    def capturar(self) -> str | None:
        """Captura segun el nodo actual. Sin cruce de contextos."""
        if self.nodo == "HETZNER_ALEMANIA":
            return self._capturar_vnc()
        elif self.nodo == "MAC":
            return self._capturar_mac()
        else:
            return self._capturar_headless()

    def _capturar_vnc(self) -> str | None:
        """Captura desde el monitor virtual de Hetzner via VNC."""
        try:
            import vncdotool.api
            import base64
            from io import BytesIO
            client = vncdotool.api.connect("127.0.0.1::5901")
            client.password(os.getenv("VNC_PWD", "ura2026"))
            img = client.captureScreen()
            client.disconnect()
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=50)
            return base64.b64encode(buf.getvalue()).decode()
        except Exception:
            return None

    def _capturar_mac(self) -> str | None:
        """Captura nativa en Mac con normalizacion Retina."""
        try:
            import base64
            from PIL import ImageGrab
            from io import BytesIO
            img = ImageGrab.grab()
            w, h = img.size
            if w > 1920 or h > 1080:
                img = img.resize((w // 2, h // 2))
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=50)
            return base64.b64encode(buf.getvalue()).decode()
        except Exception:
            return None

    def _capturar_headless(self) -> None:
        """ASUS GX10: modo headless. Sin captura real."""
        return None

    def normalizar_coordenadas(self, x: int, y: int) -> tuple[int, int]:
        """Convierte coordenadas Mac Retina a reales."""
        if self.nodo == "MAC":
            return x // 2, y // 2
        return x, y


# Mantener compatibilidad hacia atras
class CapturadorPantallaSeguro(CapturadorTarget):
    pass

def capturar_pantalla():
    """Funcion de acceso directo (compatibilidad)."""
    c = CapturadorTarget()
    return c.capturar()

def normalizar_coordenadas(x: int, y: int) -> tuple[int, int]:
    c = CapturadorTarget()
    return c.normalizar_coordenadas(x, y)

def analizar_con_ollama(imagen_b64: str | None = None, prompt: str = "") -> str:
    from scripts.pro.uitars_gx10 import analizar_con_ollama as _ollama
    return _ollama(imagen_b64, prompt)

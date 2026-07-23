#!/usr/bin/env python3
"""uitars_hetzner.py — UI-TARS en Hetzner conectado al monitor visual VNC.
Requiere: pip install ui-tars pyautogui pillow vncdotool.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from motor.cli.public_api import get_secret

VNC_HOST = "127.0.0.1"
VNC_PORT = 5900
VNC_PASS = get_secret("VNC_PWD", "ura2026")
REPORTS_DIR = Path("/root/reports")


def conectar_vnc():
    """Conecta al monitor visual via VNC y devuelve un screenshot."""
    try:
        import base64
        from io import BytesIO

        import vncdotool.api

        client = vncdotool.api.connect(f"{VNC_HOST}::{VNC_PORT}")
        client.password(VNC_PASS)

        from PIL import Image

        img = client.captureScreen()
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=50)
        b64 = base64.b64encode(buf.getvalue()).decode()
        client.disconnect()
        return b64
    except ImportError:
        import base64

        import mss

        with mss.mss() as sct:
            from io import BytesIO

            from PIL import Image

            img = sct.grab(sct.monitors[1])
            pil_img = Image.frombytes("RGB", img.size, img.rgb)
            buf = BytesIO()
            pil_img.save(buf, format="JPEG", quality=50)
            return base64.b64encode(buf.getvalue()).decode()


def main() -> None:
    # 1. Capturar del VNC
    screenshot = conectar_vnc()

    # 2. Analizar con UI-TARS
    try:
        from ui_tars import UI_TARS

        model = UI_TARS(model_name="ui-tars-1.5-7b")
        resultado = model.analyze(screenshot, "Describe la interfaz y detecta elementos interactivos")
    except Exception as e:
        resultado = f"Error: {e}"

    # 3. Guardar
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"uitars_analisis_{time.strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(json.dumps({"timestamp": time.time(), "resultado": resultado}, indent=2))


if __name__ == "__main__":
    main()

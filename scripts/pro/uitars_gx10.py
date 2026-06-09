#!/usr/bin/env python3
"""uitars_gx10.py — UI-TARS para GX10 con fallback Ollama vision.
Tres modos segun disponibilidad:
  1. Display real → captura con mss + ui-tars
  2. Xvfb → framebuffer virtual + ui-tars
  3. Sin display → modo archivo, analiza imagenes con Ollama vision
"""
from __future__ import annotations
import json, os, subprocess, sys, time, base64
from datetime import datetime
from pathlib import Path
from io import BytesIO

REPORTS_DIR = Path("/home/ramon/URA/reports")
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

def tiene_display() -> bool:
    """Verifica si hay un display disponible (real o virtual)."""
    return bool(os.environ.get("DISPLAY"))

def iniciar_xvfb() -> bool:
    """Intenta iniciar un framebuffer virtual (Xvfb)."""
    if not shutil.which("Xvfb"):
        return False
    try:
        subprocess.run(["Xvfb", ":99", "-screen", "0", "1280x720x24"], 
                      capture_output=True, timeout=5)
        os.environ["DISPLAY"] = ":99"
        time.sleep(1)
        return True
    except: return False

def capturar_pantalla() -> str | None:
    """Captura pantalla actual o virtual."""
    try:
        import mss
        with mss.mss() as sct:
            from PIL import Image
            img = sct.grab(sct.monitors[1])
            pil_img = Image.frombytes("RGB", img.size, img.rgb)
            buf = BytesIO()
            pil_img.save(buf, format="JPEG", quality=50)
            return base64.b64encode(buf.getvalue()).decode()
    except Exception as e:
        print(f"  ⚠️ Captura fallo: {e}")
        return None

def analizar_con_ollama(imagen_b64: str | None, prompt: str) -> str:
    """Analiza con Ollama vision local (llama3.2-vision:11b)."""
    import urllib.request
    data = {"model": "llama3.2-vision:11b", "prompt": prompt, "stream": False}
    if imagen_b64:
        data["images"] = [imagen_b64]
    
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:11434/api/generate",
            data=json.dumps(data).encode(),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=120) as r:
            resp = json.loads(r.read())
            return resp.get("response", "")
    except Exception as e:
        return f"Error Ollama: {e}"

def main():
    import shutil
    print("=== UI-TARS GX10 ===")
    
    # Detectar modo de operacion
    modo = "headless"
    if tiene_display():
        modo = "display"
    elif iniciar_xvfb():
        modo = "xvfb"
    
    print(f"  Modo: {modo}")
    imagen = capturar_pantalla() if modo != "headless" else None
    
    if imagen:
        print(f"  Captura: {len(imagen)} bytes")
    
    print("  Analizando con Ollama vision...")
    resultado = analizar_con_ollama(imagen, "Describe esta interfaz en detalle, lista los elementos interactivos")
    print(f"  Resultado: {resultado[:200]}")
    
    path = REPORTS_DIR / f"uitars_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(json.dumps({"modo": modo, "timestamp": time.time(), "resultado": resultado}, indent=2))
    print(f"  Reporte: {path}")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""uitars_gx10.py — UI-TARS para GX10 con fallback Ollama vision.
Si ui-tars no puede cargar el modelo (ARM64/memoria), usa llama3.2-vision:11b.
"""
from __future__ import annotations
import json, os, subprocess, sys, time
from pathlib import Path

def analizar_con_ollama(imagen_b64: str, prompt: str) -> str:
    """Fallback: analiza imagen con Ollama vision local."""
    import urllib.request
    data = json.dumps({
        "model": "llama3.2-vision:11b",
        "prompt": prompt,
        "images": [imagen_b64],
        "stream": False
    }).encode()
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:11434/api/generate",
            data=data, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read()).get("response", "")
    except Exception as e:
        return f"Error Ollama: {e}"

def capturar_pantalla() -> str:
    """Captura la pantalla actual y devuelve base64."""
    import mss, base64
    with mss.mss() as sct:
        img = sct.grab(sct.monitors[1])
        from PIL import Image
        pil_img = Image.frombytes("RGB", img.size, img.rgb)
        from io import BytesIO
        buf = BytesIO()
        pil_img.save(buf, format="JPEG", quality=50)
        return base64.b64encode(buf.getvalue()).decode()

def ejecutar_accion(accion: str, x: int = 0, y: int = 0, texto: str = "") -> bool:
    """Ejecuta una accion en la interfaz: click, type, scroll."""
    import pyautogui
    try:
        if accion == "click":
            pyautogui.click(x, y)
        elif accion == "type":
            pyautogui.write(texto)
        elif accion == "scroll":
            pyautogui.scroll(y)
        return True
    except: return False

def main():
    print("=== UI-TARS GX10 (modo headless + Ollama fallback) ===")
    
    # 1. Capturar pantalla
    print("[1/3] Capturando pantalla...")
    screenshot = capturar_pantalla()
    print(f"       {len(screenshot)} bytes (base64)")
    
    # 2. Analizar con UI-TARS o fallback Ollama
    print("[2/3] Analizando...")
    try:
        from ui_tars import UI_TARS
        model = UI_TARS(model_name="ui-tars-1.5-7b")
        resultado = model.analyze(screenshot, "Describe la interfaz")
        print(f"       UI-TARS: {resultado[:100]}")
    except Exception as e:
        print(f"       UI-TARS no disponible ({e}), usando Ollama vision...")
        resultado = analizar_con_ollama(screenshot, "Describe esta interfaz en detalle")
        print(f"       Ollama: {resultado[:100]}")
    
    # 3. Guardar resultado
    Path("/home/ramon/URA/reports/uitars_analisis.json").write_text(
        json.dumps({"timestamp": time.time(), "resultado": resultado}, indent=2)
    )
    print(f"[3/3] Analisis guardado en reports/uitars_analisis.json")
    return resultado

if __name__ == "__main__":
    main()

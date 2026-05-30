#!/usr/bin/env python3
"""Agente de Videos — Genera guiones y videos de marketing con IA."""

import json
import subprocess
import sys
import os
from pathlib import Path

BASE = Path.home() / "URA" / "ura_ia_1972"
GX10_URL = "http://10.164.1.99:11434/api/chat"
MODEL = "qwen3:32b"
OUTPUT_DIR = BASE / "docs" / "marketing" / "videos"


def generar_guion(tema: str, duracion: int = 30) -> str:
    prompt = f"Eres un director creativo. Genera un guion de {duracion}s para un Reel de Instagram de un bar de copas en Pamplona. Tema: {tema}. Incluye: escenas, texto en pantalla, CTA. Responde solo con el guion."
    payload = json.dumps(
        {"model": MODEL, "messages": [{"role": "user", "content": prompt}], "stream": False}
    )
    try:
        r = subprocess.run(
            ["curl", "-s", GX10_URL, "-d", payload], capture_output=True, text=True, timeout=60
        )
        if r.returncode == 0:
            return json.loads(r.stdout).get("message", {}).get("content", "")
    except:
        pass
    return ""


def crear_video_invideo(guion: str, titulo: str) -> str:
    api_key = os.getenv("INVIDEO_API_KEY", "")
    if not api_key:
        return ""
    payload = json.dumps({"prompt": guion, "title": titulo, "duration": 30})
    result = subprocess.run(
        [
            "curl",
            "-s",
            "-X",
            "POST",
            "https://api.invideo.io/v4/videos",
            "-H",
            f"Authorization: Bearer {api_key}",
            "-H",
            "Content-Type: application/json",
            "-d",
            payload,
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode == 0:
        return json.loads(result.stdout).get("video_url", "")
    return ""


if __name__ == "__main__":
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    tema = sys.argv[1] if len(sys.argv) > 1 else "coctel de verano"
    print(f"  Generando guion para: {tema}")
    guion = generar_guion(tema)
    if guion:
        guion_path = OUTPUT_DIR / f"guion_{tema.replace(' ', '_')[:30]}.txt"
        with open(guion_path, "w") as f:
            f.write(guion)
        print(f"  OK Guion: {guion_path.name}")
        if os.getenv("INVIDEO_API_KEY"):
            print("  Creando video con Invideo AI...")
            url = crear_video_invideo(guion, tema)
            if url:
                print(f"  OK Video: {url}")
            else:
                print("  No se pudo crear el video")
        else:
            print("  INVIDEO_API_KEY no configurada. Solo guion generado.")
    print("OK Agente de videos completado")

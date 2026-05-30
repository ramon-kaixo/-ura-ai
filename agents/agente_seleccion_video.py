#!/usr/bin/env python3
"""Agente de Seleccion de Videos — Presenta candidatos, descarga el elegido."""

import json
import sys
import subprocess
from pathlib import Path

BASE = Path.home() / "URA" / "ura_ia_1972"
BUZO_DIR = BASE / "sandbox" / "Aprendizaje" / "Enjambre" / "buzos"
OUTPUT_DIR = BASE / "knowledge" / "media"


def presentar_candidatos(resultados_file: str) -> list:
    with open(resultados_file) as f:
        data = json.load(f)
    if not data:
        print("❌ No se encontraron videos")
        return []
    print(f"🎥 {len(data)} videos candidatos:\n")
    for i, v in enumerate(data):
        title = v.get("titulo", "sin titulo")[:80]
        url = v.get("url", "sin URL")
        score = v.get("score", 0)
        print(f"  [{i + 1}] {title}")
        print(f"      Puntuacion: {score} | URL: {url[:100]}")
        print()
    return data


def guardar_seleccionados(data: list, seleccion: str):
    indices = [int(x.strip()) - 1 for x in seleccion.split(",") if x.strip().isdigit()]
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for idx in indices:
        if 0 <= idx < len(data):
            item = data[idx]
            url = item.get("url", "")
            subprocess.run(
                ["bash", str(BUZO_DIR / "buzo_video_traductor.sh"), url, "es"], check=False
            )


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: agente_seleccion_video.py <resultados.json> <indices>")
        sys.exit(1)
    resultados_file = sys.argv[1]
    seleccion = sys.argv[2]
    with open(resultados_file) as f:
        data = json.load(f)
    guardar_seleccionados(data, seleccion)

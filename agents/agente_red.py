#!/usr/bin/env python3
"""Agente de Red — Analiza y optimiza la red local con IA."""

import json
import subprocess
from pathlib import Path
from datetime import datetime

BASE = Path.home() / "URA" / "ura_ia_1972"
GX10_URL = "http://10.164.1.99:11434/api/chat"
MODEL = "qwen3:32b"
INFORMES_DIR = BASE / "sandbox" / "Aprendizaje" / "Enjambre" / "informes"


def analizar(datos: str) -> dict:
    prompt = f"""Eres un administrador de redes experto. Analiza estos datos de dispositivos y latencia. Sugiere: que dispositivos necesitan IP fija, si hay congestión o latencia anormal, recomendaciones para router virtual, y si hay dispositivos desconocidos.\nDATOS:\n{datos[:3000]}"""
    payload = json.dumps(
        {"model": MODEL, "messages": [{"role": "user", "content": prompt}], "stream": False}
    )
    try:
        r = subprocess.run(
            ["curl", "-s", GX10_URL, "-d", payload], capture_output=True, text=True, timeout=60
        )
        if r.returncode == 0:
            return json.loads(json.loads(r.stdout)["message"]["content"])
    except:
        pass
    return {}


if __name__ == "__main__":
    datos = ""
    for f in sorted(INFORMES_DIR.glob("hallazgos_red_*.json")):
        with open(f) as fp:
            datos += fp.read()[:3000] + "\n"
    analisis = analizar(datos)
    output = BASE / "docs" / "red" / f"analisis_red_{datetime.now().strftime('%Y%m%d')}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w") as f:
        json.dump(analisis, f, ensure_ascii=False, indent=2)
    print(f"OK docs/red/analisis_red_{datetime.now().strftime('%Y%m%d')}.json")

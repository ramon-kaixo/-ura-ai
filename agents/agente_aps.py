#!/usr/bin/env python3
"""Agente de APs — Gestiona, respalda y optimiza puntos de acceso WiFi."""

import json
import subprocess
from pathlib import Path
from datetime import datetime

BASE = Path.home() / "URA" / "ura_ia_1972"
GX10_URL = "http://10.164.1.99:11434/api/chat"
MODEL = "qwen3:32b"


def analizar(datos):
    prompt = f"Eres un administrador WiFi. Analiza: canales congestionados? APs con pocos clientes? Rogue APs? Canales recomendados?\nDATOS:\n{datos[:3000]}"
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
    for f in sorted((BASE / "sandbox/Aprendizaje/Enjambre/informes").glob("hallazgos_aps_*.json")):
        with open(f) as fp:
            datos += fp.read()[:3000] + "\n"
    analisis = analizar(datos)
    out = BASE / "docs" / "aps" / f"analisis_{datetime.now().strftime('%Y%m%d')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        json.dump(analisis, f, ensure_ascii=False, indent=2)
    print(f"OK {out.name}")

#!/usr/bin/env python3
"""Agente de Sugerencias Estrategicas — Analiza eventos y tendencias gastronomicas."""

import json
import subprocess
from pathlib import Path

BASE = Path.home() / "URA" / "ura_ia_1972"
GX10_URL = "http://10.164.1.99:11434/api/chat"
MODEL = "qwen3:32b"
INFORMES_DIR = BASE / "sandbox" / "Aprendizaje" / "Enjambre" / "informes"


def generar_sugerencias(datos_eventos: str, datos_tendencias: str) -> dict:
    prompt = f"""Eres un consultor gastronomico experto en el mercado espanol. Genera UNICAMENTE un JSON con: sugerencias (3-5 acciones concretas para un bar en Pamplona), proximos_eventos (2-3 eventos a monitorizar), tendencias_a_aplicar (2-3 tendencias de bajo coste), alerta_competencia (si hay algo urgente).\n\nEVENTOS:\n{datos_eventos[:3000]}\n\nTENDENCIAS:\n{datos_tendencias[:2000]}"""
    payload = json.dumps(
        {"model": MODEL, "messages": [{"role": "user", "content": prompt}], "stream": False}
    )
    try:
        result = subprocess.run(
            ["curl", "-s", GX10_URL, "-d", payload], capture_output=True, text=True, timeout=90
        )
        if result.returncode == 0:
            content = json.loads(result.stdout)["message"]["content"]
            return json.loads(content)
    except:
        pass
    return {}


if __name__ == "__main__":
    datos_eventos = ""
    datos_tendencias = ""
    for f in sorted(INFORMES_DIR.glob("hallazgos_prensa_*.json")):
        with open(f) as fp:
            datos_eventos += fp.read()[:3000] + "\n"
    for f in sorted(INFORMES_DIR.glob("hallazgos_bares_*.json")):
        with open(f) as fp:
            datos_tendencias += fp.read()[:2000] + "\n"
    sugerencias = generar_sugerencias(datos_eventos, datos_tendencias)
    today = __import__("datetime").datetime.now().strftime("%Y%m%d")
    output = BASE / "docs" / f"sugerencias_estrategicas_{today}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w") as f:
        json.dump(sugerencias, f, ensure_ascii=False, indent=2)
    print(f"✅ {len(sugerencias)} categorias en {output.name}")
    for k, v in sugerencias.items():
        print(f"  {k}: {len(v) if isinstance(v, list) else 1} items")

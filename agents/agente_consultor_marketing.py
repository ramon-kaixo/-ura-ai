#!/usr/bin/env python3
"""Agente Consultor de Marketing — Simula agencia especializada en hosteleria."""

import json
import subprocess
from pathlib import Path
from datetime import datetime

BASE = Path.home() / "URA" / "ura_ia_1972"
GX10_URL = "http://10.164.1.99:11434/api/chat"
MODEL = "qwen3:32b"
INFORMES_DIR = BASE / "sandbox" / "Aprendizaje" / "Enjambre" / "informes"
OUTPUT_DIR = BASE / "docs" / "marketing"


def generar_plan(datos_competencia: str, datos_tendencias: str) -> dict:
    prompt = f"""Eres un consultor de marketing gastronomico senior (TastyGrowth, ChefDigital, WEKOOK). Genera UNICAMENTE un JSON con plan de marketing completo para bar de copas en Pamplona: objetivos, publico objetivo, estrategia contenido, plan publicaciones, estrategia video, diseno carta digital, gestion resenas, plan fidelizacion.

DATOS COMPETENCIA:\n{datos_competencia[:3000]}
DATOS TENDENCIAS:\n{datos_tendencias[:2000]}"""
    payload = json.dumps(
        {"model": MODEL, "messages": [{"role": "user", "content": prompt}], "stream": False}
    )
    try:
        r = subprocess.run(
            ["curl", "-s", GX10_URL, "-d", payload], capture_output=True, text=True, timeout=90
        )
        if r.returncode == 0:
            return json.loads(json.loads(r.stdout)["message"]["content"])
    except:
        pass
    return {}


if __name__ == "__main__":
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    datos_competencia = ""
    datos_tendencias = ""
    for f in sorted(INFORMES_DIR.glob("hallazgos_bares_copas_*.json")):
        with open(f) as fp:
            datos_competencia += fp.read()[:3000]
    for f in sorted(INFORMES_DIR.glob("hallazgos_tendencias_locales_*.json")):
        with open(f) as fp:
            datos_tendencias += fp.read()[:2000]
    plan = generar_plan(datos_competencia, datos_tendencias)
    output = OUTPUT_DIR / f"plan_marketing_{datetime.now().strftime('%Y%m%d')}.json"
    with open(output, "w") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)
    print(f"OK Plan de marketing en {output.name}")
    for k, v in plan.items():
        print(f"  {k}: {len(v) if isinstance(v, list) else 1} items")

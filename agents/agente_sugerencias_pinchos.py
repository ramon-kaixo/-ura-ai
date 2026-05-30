#!/usr/bin/env python3
import json
import subprocess
from pathlib import Path

BASE = Path.home() / "URA" / "ura_ia_1972"
GX10_URL = "http://10.164.1.99:11434/api/chat"
MODEL = "qwen3:32b"
INFORMES_DIR = BASE / "sandbox" / "Aprendizaje" / "Enjambre" / "informes"


def generar_sugerencias(datos_competencia: str, datos_eventos: str) -> list:
    prompt = f"""Eres un chef creativo especializado en cocina espanola y navarra. Analiza los siguientes datos de competencia y eventos gastronomicos. Genera 5 sugerencias de pinchos nuevos y originales. Para cada pincho indica: nombre creativo, 3 ingredientes principales, por que funcionaria en Pamplona, y precio sugerido entre 2€ y 5€. Responde UNICAMENTE con un JSON.\n\nDATOS DE COMPETENCIA:\n{datos_competencia[:3000]}\n\nDATOS DE EVENTOS:\n{datos_eventos[:3000]}"""
    payload = json.dumps(
        {"model": MODEL, "messages": [{"role": "user", "content": prompt}], "stream": False}
    )
    try:
        result = subprocess.run(
            ["curl", "-s", GX10_URL, "-d", payload], capture_output=True, text=True, timeout=90
        )
        if result.returncode == 0:
            content = json.loads(result.stdout)["message"]["content"]
            return json.loads(content) if isinstance(json.loads(content), list) else []
    except:
        pass
    return []


if __name__ == "__main__":
    datos_comp = ""
    datos_eventos = ""
    for f in sorted(INFORMES_DIR.glob("hallazgos_bares_*.json")):
        with open(f) as fp:
            datos_comp += fp.read()[:3000] + "\n"
    for f in sorted(INFORMES_DIR.glob("hallazgos_prensa_*.json")):
        with open(f) as fp:
            datos_eventos += fp.read()[:3000] + "\n"
    sugerencias = generar_sugerencias(datos_comp, datos_eventos)
    today = __import__("datetime").datetime.now().strftime("%Y%m%d")
    output = BASE / "docs" / f"sugerencias_pinchos_{today}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w") as f:
        json.dump(sugerencias, f, ensure_ascii=False, indent=2)
    print(f"✅ {len(sugerencias)} sugerencias de pinchos en {output.name}")

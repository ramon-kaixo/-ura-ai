#!/usr/bin/env python3
"""Agente de Marketing Automatizado — Genera contenido para redes, cartas, letreros."""

import json
import subprocess
import sys
from pathlib import Path

BASE = Path.home() / "URA" / "ura_ia_1972"
GX10_URL = "http://10.164.1.99:11434/api/chat"
MODEL = "qwen3:32b"

PROMPTS = {
    "post_instagram": "Eres un experto en marketing para hosteleria. Genera un post de Instagram para un bar de copas en Pamplona. Incluye: texto del post, hashtags (max 10), emoji sugerido, hora recomendada. DATOS:\n{}",
    "video_reel": "Eres un director creativo. Guion de 30s para Reel de Instagram para un bar de copas. Incluye: 3-5 escenas, texto en pantalla, musica sugerida, CTA. TEMA:\n{}",
    "letrero_digital": "Eres disenador de senalizacion digital. Contenido para letrero digital de bar de copas. Incluye: titulo, subtitulo, 3-5 elementos con precios, colores. TEMA:\n{}",
    "carta_digital": "Eres disenador de menus. Carta digital para bar de copas. Incluye: secciones (cocteles, copas, gin tonic), 3-5 productos por seccion con descripcion y precio.\n{}",
    "promocion": "Eres experto en promociones. Disena una promocion para bar de copas. Incluye: nombre, descripcion, duracion, precio especial, estrategia redes.\n{}",
}


def generar(tipo: str, datos: str) -> dict:
    prompt = PROMPTS.get(tipo, PROMPTS["post_instagram"]).format(datos[:2000])
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
    tipo = sys.argv[1] if len(sys.argv) > 1 else "post_instagram"
    tema = sys.argv[2] if len(sys.argv) > 2 else "cocteles artesanos"

    informes = BASE / "sandbox" / "Aprendizaje" / "Enjambre" / "informes"
    datos = tema
    for f in sorted(informes.glob("hallazgos_bares_copas_*.json")):
        with open(f) as fp:
            datos += "\n" + fp.read()[:1000]

    contenido = generar(tipo, datos)
    ts = __import__("datetime").datetime.now().strftime("%Y%m%d_%H%M%S")
    output = BASE / "docs" / "marketing" / f"{tipo}_{ts}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w") as f:
        json.dump(contenido, f, ensure_ascii=False, indent=2)
    print(f"✅ {tipo} generado en {output.name}")

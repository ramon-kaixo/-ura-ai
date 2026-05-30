#!/usr/bin/env python3
"""Agente de Flota — Analiza y toma decisiones sobre la flota."""

import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime

BASE = Path.home() / "URA" / "ura_ia_1972"
GX10_URL = "http://10.164.1.99:11434/api/chat"
MODEL = "qwen3:32b"


def analizar(datos):
    prompt = f"Eres un administrador de sistemas. Analiza estos datos de flota: dispositivos con disco >80%? offline? diferencias entre OS? Prioriza acciones.\nDATOS:\n{datos[:3000]}"
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


def tomar_decisiones(datos):
    prompt = f'Eres el gestor de flota. Decide: que dispositivos actualizar, que paquete (caja/musica/general), urgencia. JSON: [{{"hostname":"...","accion":"actualizar|esperar|revisar","paquete":"caja|musica|general","urgencia":"alta|media|baja"}}]\nDATOS:\n{datos[:3000]}'
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
    return []


def ejecutar(decisiones):
    for d in decisiones:
        host, accion, paq = d.get("hostname", ""), d.get("accion", ""), d.get("paquete", "general")
        if accion == "actualizar":
            print(f"   📦 {host}: {paq}")
            subprocess.run(
                ["bash", str(BASE / "scripts/desplegar_flota.sh"), "--host", host, "--paquete", paq]
            )
        elif accion == "revisar":
            print(f"   ⚠️ {host}: revision manual")
        else:
            print(f"   ✅ {host}: sin cambios")


if __name__ == "__main__":
    datos = ""
    for f in sorted(
        (BASE / "sandbox/Aprendizaje/Enjambre/informes").glob("hallazgos_flota_*.json")
    ):
        with open(f) as fp:
            datos += fp.read()[:3000] + "\n"
    modo = sys.argv[1] if len(sys.argv) > 1 else "analizar"
    if modo == "decisiones":
        dec = tomar_decisiones(datos)
        out = BASE / "docs" / "flota" / f"decisiones_{datetime.now().strftime('%Y%m%d')}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w") as f:
            json.dump(dec, f, ensure_ascii=False, indent=2)
        print(f"🧠 {len(dec)} decisiones")
        ejecutar(dec)
    else:
        r = analizar(datos)
        out = BASE / "docs" / "flota" / f"analisis_{datetime.now().strftime('%Y%m%d')}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w") as f:
            json.dump(r, f, ensure_ascii=False, indent=2)
        print(f"OK {out.name}")

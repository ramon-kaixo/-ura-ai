#!/usr/bin/env python3
"""Agente de Sistema — Analiza, decide y actua sobre la salud del sistema."""

import json
import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime

BASE = Path.home() / "URA" / "ura_ia_1972"
GX10_URL = os.getenv("GX10_URL", "http://10.164.1.99:11434/api/chat")
MODEL = "qwen3:32b"


def disk_usage(path):
    r = subprocess.run(["du", "-sm", path], capture_output=True, text=True, timeout=10)
    return int(r.stdout.split()[0]) if r.returncode == 0 else 0


def command_exists(cmd):
    return subprocess.run(["which", cmd], capture_output=True).returncode == 0


def analizar(datos):
    prompt = f"Eres un administrador de sistemas. Analiza estos datos: hay archivos que limpiar? riesgos de seguridad? se puede liberar espacio? prioriza acciones por impacto.\nDATOS:\n{datos[:3000]}"
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


def limpiar():
    r = {}
    temp_antes = disk_usage("/tmp")
    subprocess.run(
        ["find", "/tmp", "-type", "f", "-mtime", "+7", "-delete"], capture_output=True, timeout=30
    )
    temp_despues = disk_usage("/tmp")
    r["tmp_liberado_mb"] = temp_antes - temp_despues
    subprocess.run(
        ["find", str(BASE), "-type", "d", "-name", "__pycache__", "-exec", "rm", "-rf", "{}", "+"],
        capture_output=True,
        timeout=30,
    )
    r["pycache"] = "limpiado"
    return r


if __name__ == "__main__":
    accion = sys.argv[1] if len(sys.argv) > 1 else "analizar"
    if accion == "analizar":
        datos = ""
        for f in sorted(
            (BASE / "sandbox/Aprendizaje/Enjambre/informes").glob("hallazgos_sistema_*.json")
        ):
            with open(f) as fp:
                datos += fp.read()[:3000] + "\n"
        analisis = analizar(datos)
        out = BASE / "docs" / "sistema" / f"analisis_{datetime.now().strftime('%Y%m%d')}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w") as f:
            json.dump(analisis, f, ensure_ascii=False, indent=2)
        print(f"OK {out.name}")
    elif accion == "limpiar":
        r = limpiar()
        print(f"OK liberados {r.get('tmp_liberado_mb', 0)} MB")

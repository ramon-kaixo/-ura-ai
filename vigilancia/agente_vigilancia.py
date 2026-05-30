#!/usr/bin/env python3
"""Agente de Vigilancia — Analisis de periodos por comando de voz."""

import json
import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime

TOKEN = os.environ.get("URA_VIGILANCIA_TOKEN", "")
if not TOKEN:
    print("Configurar URA_VIGILANCIA_TOKEN")
    sys.exit(1)

BASE = Path.home() / "URA" / "ura_ia_1972"
GX10_URL = "http://10.164.1.99:11434/api/chat"
MODEL = "qwen3:32b"


def interpretar(texto: str) -> dict:
    prompt = f"""Eres un sistema de vigilancia. Interpreta: "{texto}"
Extrae UNICAMENTE un JSON con: accion (analizar_periodo|conteo_clientes|aprender|estado), camara (opcional), inicio (YYYY-MM-DDTHH:MM:SS), fin (YYYY-MM-DDTHH:MM:SS). Si no se especifica camara, usa 'barra'. Si no se especifica fecha, usa hoy."""
    payload = json.dumps(
        {"model": MODEL, "messages": [{"role": "user", "content": prompt}], "stream": False}
    )
    try:
        r = subprocess.run(
            ["curl", "-s", GX10_URL, "-d", payload], capture_output=True, text=True, timeout=30
        )
        if r.returncode == 0:
            return json.loads(json.loads(r.stdout)["message"]["content"])
    except:
        pass
    return {"accion": "error"}


def ejecutar(cmd: dict) -> str:
    if cmd.get("accion") == "analizar_periodo":
        camara = cmd.get("camara", "barra")
        inicio = cmd.get("inicio", datetime.now().replace(hour=17, minute=0).isoformat())
        fin = cmd.get("fin", datetime.now().replace(hour=18, minute=30).isoformat())
        r = subprocess.run(
            ["bash", str(BASE / "scripts" / "analizar_periodo.sh"), camara, inicio, fin],
            capture_output=True,
            text=True,
            timeout=300,
        )
        return r.stdout.strip() or "Analisis completado"
    elif cmd.get("accion") == "conteo_clientes":
        modelo = BASE / "knowledge" / "modelo_patrones" / "patrones.json"
        if modelo.exists():
            with open(modelo) as f:
                d = json.load(f)
            return f"📊 {d.get('total_eventos', 0)} eventos registrados en {len(d.get('ocupacion_por_hora', {}))} franjas"
        return "Sin datos de patrones aun"
    return "Comando no reconocido"


if __name__ == "__main__":
    if "--token" in sys.argv:
        idx = sys.argv.index("--token")
        if idx + 1 >= len(sys.argv) or sys.argv[idx + 1] != TOKEN:
            print("Token invalido")
            sys.exit(1)
        sys.argv = sys.argv[:idx] + sys.argv[idx + 2 :]
    texto = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "analiza el bar de 5 a 6 de la tarde"
    cmd = interpretar(texto)
    print(ejecutar(cmd))

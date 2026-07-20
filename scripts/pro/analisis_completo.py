#!/usr/bin/env python3
"""analisis_completo.py — Analisis integral de URA (estado + monologo + acciones).

FUSIONADO CON:
  - analisis_llm.py (analisis de estado del sistema con LLM)
  - meta_mejora_v2.py (analisis de monologo interno)
  - reflexion_ura.py (reflexion sobre acciones)
"""

PLUGIN = {
    "name": "analisis_completo",
    "phase": "post",
    "timeout": 60,
    "blocking": False,
    "needs_file": False,
}

import contextlib
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

MODEL_ROUTER = os.environ.get("MODEL_ROUTER_URL", os.environ.get("MODEL_ROUTER_URL", "http://10.164.1.99:11435"))
LOG = Path.home() / "URA/ura_ia_1972/logs/analisis_completo.log"
SUGERENCIAS = Path("/opt/ura/data/sugerencias.json")
MONOLOGO = Path("/opt/ura/data/monologo_interno.json")
REFLEXIONES = Path("/opt/ura/data/reflexiones.log")
ACCIONES = Path("/opt/ura/data/cola_acciones.json")
MEJORAS = Path("/opt/ura/config/prompts/mejoras.txt")


def log(msg) -> None:
    with open(LOG, "a") as f:  # noqa: PTH123
        f.write(f"{datetime.now(UTC).isoformat()} - {msg}\n")


def llm(prompt, model="auto"):
    try:
        payload = json.dumps(
            {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "temperature": 0.3,
            },
        ).encode()
        req = urllib.request.Request(  # noqa: S310
            f"{MODEL_ROUTER}/v1/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json", "Authorization": "Bearer local"},
        )
        with urllib.request.urlopen(req, timeout=120) as r:  # noqa: S310
            data = json.loads(r.read())
        return data.get("choices", [{}])[0].get("message", {}).get("content", "")
    except Exception as e:
        return f"Error: {e}"


def recopilar_estado():
    estado = {}
    try:
        r = subprocess.run(["uptime"], capture_output=True, text=True, timeout=5, check=False)
        estado["mac_uptime"] = r.stdout.strip()
    except Exception:
        estado["mac_uptime"] = "error"
    try:
        r = subprocess.run(
            [
                "ssh",
                "-o",
                "ConnectTimeout=5",
                os.environ.get("ASUS_SSH", "ramon@10.164.1.99"),
                "uptime && free -h | head -2 && docker ps --format '{{.Names}}: {{.Status}}' && systemctl is-active ollama model-router",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        estado["gx10"] = r.stdout.strip()
    except Exception:
        estado["gx10"] = "no alcanzable"
    try:
        r = subprocess.run(
            ["curl", "-s", "-m", "3", "http://127.0.0.1:9091/"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        estado["mcp"] = "activo" if r.stdout else "no responde"
    except Exception:
        estado["mcp"] = "no responde"
    try:
        r = subprocess.run(
            ["curl", "-s", "-m", "3", "http://127.0.0.1:18789/"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        estado["openclaw"] = "activo" if "html" in r.stdout.lower() else "no responde"
    except Exception:
        estado["openclaw"] = "no responde"
    return estado


def analizar_monologo():
    if not MONOLOGO.exists():
        return {"status": "no existe", "sugerencias": []}
    with open(MONOLOGO) as f:  # noqa: PTH123
        acciones = json.load(f)
    if len(acciones) < 10:
        return {"status": "pocos datos", "total": len(acciones), "sugerencias": []}
    tipos = {}
    fallos = []
    for a in acciones:
        t = a.get("tipo", "?")
        tipos[t] = tipos.get(t, 0) + 1
        if not a.get("ok", False):
            fallos.append(a)
    sugerencias = []
    menos_usada = min(tipos, key=tipos.get) if tipos else None
    if menos_usada and tipos[menos_usada] < len(acciones) * 0.1:
        sugerencias.append(f"Bajo uso de '{menos_usada}' ({tipos[menos_usada]} veces)")
    if fallos:
        sugerencias.append(f"{len(fallos)} fallos detectados en monologo")
    if tipos.get("ejecutar", 0) > 20:
        sugerencias.append("Alta frecuencia de ejecutar — considerar tools especificas")
    return {
        "status": "ok",
        "total": len(acciones),
        "distribucion": tipos,
        "fallos": len(fallos),
        "sugerencias": sugerencias,
    }


def reflexionar_acciones():
    if not ACCIONES.exists():
        return {"status": "sin acciones", "reflexion": "No hay acciones para analizar"}
    with open(ACCIONES) as f:  # noqa: PTH123
        acciones = json.load(f)
    ultimas = acciones[-10:]
    exitosos = sum(1 for a in ultimas if a.get("ok", False))
    fallidos = sum(1 for a in ultimas if not a.get("ok", True))
    tipos = {}
    for a in ultimas:
        tipo = a.get("tipo", "desconocido")
        tipos[tipo] = tipos.get(tipo, 0) + 1
    reflexion = f"Ultimas {len(ultimas)} acciones: {exitosos} exitos, {fallidos} fallos"
    sugerencias = []
    if fallidos > exitosos:
        reflexion += " — Alta tasa de fallos"
        sugerencias.append("Revisar herramientas MCP/API y permisos")
    with open(REFLEXIONES, "a") as f:  # noqa: PTH123
        f.write(f"{datetime.now(UTC).isoformat()} - {reflexion}\n")
    return {
        "status": "ok",
        "total": len(ultimas),
        "exitosos": exitosos,
        "fallidos": fallidos,
        "distribucion": tipos,
        "sugerencias": sugerencias,
    }


def guardar_sugerencia(analisis) -> None:
    sugs = []
    if SUGERENCIAS.exists():
        with contextlib.suppress(BaseException):
            sugs = json.loads(SUGERENCIAS.read_text())
    sugs.append(
        {
            "timestamp": time.time(),
            "dominio": "analisis_completo",
            "analisis": analisis[:500],
        },
    )
    if len(sugs) > 100:
        sugs = sugs[-50:]
    SUGERENCIAS.parent.mkdir(parents=True, exist_ok=True)
    SUGERENCIAS.write_text(json.dumps(sugs, indent=2, ensure_ascii=False))


def scan_project() -> None:
    from pathlib import Path as _Path

    root = _Path.home() / "URA/ura_ia_1972"
    list(root.rglob("*.py"))


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Analisis integral de URA")
    parser.add_argument("--scan", action="store_true", help="Escanear todo el proyecto")
    args = parser.parse_args()
    if args.scan:
        scan_project()
        return 0

    log("=" * 50)
    log("ANALISIS COMPLETO DE URA")
    log("=" * 50)

    log("\n--- 1. Estado del Sistema ---")
    estado = recopilar_estado()
    for k, v in estado.items():
        log(f"  {k}: {str(v)[:100]}")

    log("\n--- 2. Analisis de Monologo ---")
    monologo = analizar_monologo()
    log(f"  Status: {monologo['status']}")
    if monologo.get("sugerencias"):
        for s in monologo["sugerencias"]:
            log(f"  {s}")

    log("\n--- 3. Reflexion de Acciones ---")
    reflexion = reflexionar_acciones()
    log(f"  {reflexion.get('reflexion', reflexion.get('status', ''))}")
    if reflexion.get("sugerencias"):
        for s in reflexion["sugerencias"]:
            log(f"  {s}")

    log("\n--- 4. Analisis LLM ---")
    prompt = f"""Eres el sistema de auto-conciencia de URA.
Analiza este estado y responde en espanol, maximo 5 lineas:

Estado: {json.dumps(estado, indent=2, ensure_ascii=False)[:500]}
Monologo: {json.dumps(monologo, indent=2, ensure_ascii=False)[:300]}
Acciones: {json.dumps(reflexion, indent=2, ensure_ascii=False)[:300]}

Responde con:
1. ESTADO: ¿todo funciona? (OK/ATENCION/PROBLEMA)
2. Si hay problemas, di cuales
3. Una mejora concreta
"""
    try:
        respuesta = llm(prompt, "auto")
        log(f"  LLM: {respuesta[:200]}")
        guardar_sugerencia(respuesta)
    except Exception as e:
        log(f"  LLM no disponible: {e}")

    log("\nAnalisis completo finalizado")
    return 0


if __name__ == "__main__":
    sys.exit(main())

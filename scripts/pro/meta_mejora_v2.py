#!/usr/bin/env python3
"""meta_mejora_v2.py — Analiza el monologo interno y sugiere mejoras al prompt de URA."""

import json
from datetime import datetime
from pathlib import Path

MONOLOGO = Path("/opt/ura/data/monologo_interno.json")
REFLEXIONES = Path("/opt/ura/data/reflexiones.log")
MEJORAS = Path("/opt/ura/config/prompts/mejoras.txt")
SUGERENCIAS = Path("/opt/ura/data/sugerencias.json")
MEJORAS.parent.mkdir(parents=True, exist_ok=True)


def log(msg):
    print(msg)
    with open(str(MEJORAS), "a") as f:
        f.write(f"# {datetime.now().isoformat()}: {msg}\n")


def sugerir(problema, solucion):
    sugs = []
    if SUGERENCIAS.exists():
        with open(SUGERENCIAS) as f:
            sugs = json.load(f)
    sugs.append(
        {
            "timestamp": datetime.now().timestamp(),
            "dominio": "meta_mejora",
            "problema": problema,
            "solucion": solucion,
        }
    )
    with open(SUGERENCIAS, "w") as f:
        json.dump(sugs, f, indent=2)


def main():
    log("=== ANALISIS META-MEJORA ===")

    if not MONOLOGO.exists():
        log("⚠️ Monologo no encontrado")
        return

    with open(MONOLOGO) as f:
        acciones = json.load(f)

    if len(acciones) < 10:
        log(f"⚠️ Pocas acciones ({len(acciones)}), esperando mas datos")
        return

    # Analizar patrones
    tipos = {}
    fallos = []
    for a in acciones:
        t = a.get("tipo", "?")
        tipos[t] = tipos.get(t, 0) + 1
        if not a.get("ok", False):
            fallos.append(a)

    total = len(acciones)
    log(f"Total acciones: {total}")
    log(f"Distribucion: {json.dumps(dict(sorted(tipos.items(), key=lambda x: -x[1])), indent=2)}")

    # Sugerencias basadas en uso
    mas_usada = max(tipos, key=tipos.get) if tipos else None
    menos_usada = min(tipos, key=tipos.get) if tipos else None

    if mas_usada:
        log(f"✅ Accion mas usada: {mas_usada} ({tipos[mas_usada]} veces)")
    if menos_usada and tipos[menos_usada] < total * 0.1:
        sugg = f"La accion '{menos_usada}' se usa poco ({tipos[menos_usada]} veces). Podria enfatizarse en el prompt."
        log(f"💡 Sugerencia: {sugg}")
        sugerir(f"Bajo uso de {menos_usada}", sugg)

    if fallos:
        log(f"❌ {len(fallos)} fallos detectados:")
        for f in fallos[-3:]:
            log(f"  - {f.get('tipo', '?')}: {str(f.get('error', ''))[:100]}")
        sugerir(
            f"{len(fallos)} fallos en acciones recientes",
            "Revisar MCP server y permisos de los agentes",
        )
    else:
        log("✅ Sin fallos — tasa de exito 100%")

    # Sugerir nueva tool si hay patron de uso
    if tipos.get("ejecutar", 0) > 20:
        sugg = "Alta frecuencia de 'ejecutar' (>20 veces). Considerar crear tools especificas."
        log(f"💡 {sugg}")
        sugerir("Optimizar tools", sugg)

    log("=== ANALISIS COMPLETADO ===")


if __name__ == "__main__":
    main()

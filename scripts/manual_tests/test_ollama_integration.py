#!/usr/bin/env python3
"""Test de integración Ollama directo en URA OpenClaw client."""

import asyncio
import sys

sys.path.insert(0, "/Users/ramonesnaola/URA/ura_ia_1972")

from core.ura_openclaw_client import OpenClawClient, detect_openclaw


async def test_integration():
    print("=== Test de Integración Ollama Directo ===\n")

    # 1. Detectar disponibilidad
    print("1. Detectando disponibilidad...")
    availability = detect_openclaw()
    print(f"   Modo: {availability.mode}")
    print(f"   Razón: {availability.reason}")
    print()

    # 2. Crear cliente
    print("2. Creando cliente...")
    client = OpenClawClient(availability=availability)
    print(f"   Cliente modo: {client.mode}")
    print(f"   Cliente is_real: {client.is_real}")
    print()

    # 3. Ejecutar búsqueda
    print("3. Ejecutando búsqueda...")
    tema = "Define brevemente qué es un agente cognitivo"
    print(f"   Tema: {tema}")
    print()

    try:
        result = await client.search(tema)
        print(f"   Estado: {result['estado']}")
        print(f"   Duración: {result['duracion_segundos']:.2f}s")
        print(f"   Modelo: {result['modelo']}")
        print(f"   OpenClaw mode: {result.get('openclaw_mode')}")
        print(f"   OpenClaw availability: {result.get('openclaw_availability')}")
        print(f"   Razonamiento: {result.get('razonamiento', '')[:200]}...")
        print()
        print("✅ Integración exitosa!")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_integration())

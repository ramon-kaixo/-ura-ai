#!/usr/bin/env python3
"""Stress-test del ConcurrentVRAMGuard (asyncio.Semaphore 2).

Lanza 6 peticiones simultáneas contra model-router. El semáforo de
tamaño 2 debe escalonar la entrada a GPU: 1-2 entran, 3-6 esperan.

Uso:
    python3 scripts/tests/stress_vram_guard.py

Monitorear:
    journalctl -u model-router.service -f | grep "VRAM"
    nvidia-smi --query-gpu=memory.used --format=csv -l 1
"""

import asyncio
import time

import httpx

URL_API = "http://127.0.0.1:11435/v1/chat/completions"


async def lanzar_peticion_concurrente(id_agente: int, payload: dict):
    inicio_total = time.time()
    print(f"[Agente {id_agente:2d}] Petición enviada al buffer...")

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(URL_API, json=payload)
            latencia_backend = time.time() - inicio_total

            if response.status_code == 200:
                print(f"✅ [Agente {id_agente:2d}] Éxito en {latencia_backend:.2f}s (Slot liberado).")
            else:
                print(f"❌ [Agente {id_agente:2d}] Error HTTP {response.status_code} tras {latencia_backend:.2f}s")

        except Exception as e:
            print(f"💥 [Agente {id_agente:2d}] Fallo de red/timeout: {str(e)[:60]}")


async def main():
    payload_test = {
        "model": "llama3.2:3b",
        "messages": [{"role": "user", "content": "Genera un texto largo sobre sistemas Linux operativos."}],
        "temperature": 0.1,
    }

    print("--- INICIANDO STRESS-TEST DE CONCURRENCIA VRAM ---")
    print(f"URL: {URL_API}")
    print(f"Modelo: {payload_test['model']}")
    print("Envío 6 peticiones simultáneas. Semáforo=2 → deben escalonarse en 3 oleadas.")
    print()

    inicio_script = time.time()
    tareas = [lanzar_peticion_concurrente(i, payload_test) for i in range(1, 7)]
    await asyncio.gather(*tareas)

    total = time.time() - inicio_script
    print("\n--- TEST FINALIZADO ---")
    print(f"Tiempo total del ciclo concurrente: {total:.2f} segundos.")
    print("6 peticiones / Semáforo=2 → ~3 oleadas esperadas.")


if __name__ == "__main__":
    asyncio.run(main())

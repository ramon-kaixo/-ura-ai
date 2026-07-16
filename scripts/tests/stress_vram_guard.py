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


async def lanzar_peticion_concurrente(id_agente: int, payload: dict) -> None:
    inicio_total = time.time()

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(URL_API, json=payload)
            time.time() - inicio_total

            if response.status_code == 200:
                pass
            else:
                pass

        except Exception:
            pass


async def main() -> None:
    payload_test = {
        "model": "llama3.2:3b",
        "messages": [{"role": "user", "content": "Genera un texto largo sobre sistemas Linux operativos."}],
        "temperature": 0.1,
    }

    inicio_script = time.time()
    tareas = [lanzar_peticion_concurrente(i, payload_test) for i in range(1, 7)]
    await asyncio.gather(*tareas)

    time.time() - inicio_script


if __name__ == "__main__":
    asyncio.run(main())

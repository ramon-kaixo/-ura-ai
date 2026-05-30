import requests
import time
import json
import threading
from pathlib import Path

NODOS = [
    {"nombre": "disk_check", "url": "http://localhost:8101/health"},
    {"nombre": "ollama_health", "url": "http://localhost:8102/health"},
]
PETICIONES = 50
CONCURRENCIA = 10
LOG = Path("logs/nodes/stress_results.jsonl")


def llamar(nodo, resultados):
    try:
        t0 = time.time()
        r = requests.get(nodo["url"], timeout=10)
        ms = round((time.time() - t0) * 1000)
        resultados.append(
            {"nodo": nodo["nombre"], "status": r.status_code, "ms": ms, "ok": r.status_code == 200}
        )
    except Exception as e:
        resultados.append(
            {"nodo": nodo["nombre"], "status": 0, "ms": 0, "ok": False, "error": str(e)}
        )


for nodo in NODOS:
    print(
        f"\n=== Estrés: {nodo['nombre']} ({PETICIONES} peticiones, {CONCURRENCIA} concurrentes) ==="
    )
    resultados = []
    for bloque in range(PETICIONES // CONCURRENCIA):
        hilos = [
            threading.Thread(target=llamar, args=(nodo, resultados)) for _ in range(CONCURRENCIA)
        ]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join()
        time.sleep(0.2)

    ok = sum(1 for r in resultados if r["ok"])
    tiempos = [r["ms"] for r in resultados if r["ok"]]
    print(f"  OK: {ok}/{PETICIONES}")
    print(f"  Latencia media: {round(sum(tiempos) / len(tiempos) if tiempos else 0)}ms")
    print(f"  Latencia máx:  {max(tiempos) if tiempos else 0}ms")
    print(f"  Errores: {PETICIONES - ok}")

    with open(LOG, "a") as f:
        f.write(
            json.dumps(
                {
                    "nodo": nodo["nombre"],
                    "ts": time.time(),
                    "ok": ok,
                    "total": PETICIONES,
                    "media_ms": round(sum(tiempos) / len(tiempos) if tiempos else 0),
                    "max_ms": max(tiempos) if tiempos else 0,
                }
            )
            + "\n"
        )

print("\n✅ Stress test completo. Resultados en logs/nodes/stress_results.jsonl")

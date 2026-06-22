#!/usr/bin/env python3
"""seed_transacciones.py — Puebla Qdrant con transacciones baseline para el alineador.
Ejecutar una vez tras migrar a Qdrant para evitar distance=1.0 en /v2/interact.
"""

import json
import math
import sys

from motor.core.config import UraConfig
from motor.core.qdrant_client import COLECCION_TRANSACCIONES, QdrantClient

TRANSACCIONES = [
    (
        "Ejecuta el script de backup en /opt/ura",
        {"intent": "ejecutar", "complexity": "simple", "domain": "sistema", "entities": ["backup.sh"]},
    ),
    (
        "Analiza el log de errores del detector de cámaras",
        {"intent": "analizar", "complexity": "media", "domain": "sistema", "entities": ["detector.log"]},
    ),
    (
        "¿Cuál es el estado del swarm de buzos?",
        {"intent": "preguntar", "complexity": "simple", "domain": "sistema", "entities": []},
    ),
    (
        "Revisa el consumo de RAM en GX10",
        {"intent": "analizar", "complexity": "simple", "domain": "sistema", "entities": ["gx10"]},
    ),
    (
        "Configura la cámara del garaje para grabación continua",
        {"intent": "configurar", "complexity": "compleja", "domain": "vision", "entities": ["garaje"]},
    ),
    (
        "Refactoriza el módulo qdrant_client para añadir búsqueda semántica",
        {"intent": "ejecutar", "complexity": "compleja", "domain": "desarrollo", "entities": ["qdrant_client.py"]},
    ),
    (
        "¿Qué servicios están caídos en ASUS?",
        {"intent": "preguntar", "complexity": "simple", "domain": "sistema", "entities": []},
    ),
    (
        "Ejecuta la tuneladora de mantenimiento",
        {"intent": "ejecutar", "complexity": "media", "domain": "sistema", "entities": ["tuneladora.sh"]},
    ),
    (
        "Explora la red 192.168.1.0/24 en busca de nuevas cámaras",
        {"intent": "explorar", "complexity": "media", "domain": "red", "entities": ["192.168.1.0/24"]},
    ),
    (
        "Actualiza las reglas del firewall para permitir Tailscale",
        {"intent": "configurar", "complexity": "media", "domain": "seguridad", "entities": ["tailscale"]},
    ),
]


def _distancia_coseno(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return 1.0 if not na or not nb else 1.0 - (dot / (na * nb))


def main() -> None:
    print("Conectando a Qdrant...")
    qdrant = QdrantClient.instancia(UraConfig.load())
    if not qdrant.disponible:
        print("ERROR: Qdrant no disponible")
        sys.exit(1)

    guardadas = 0
    distancias = []
    for i, (raw, structure) in enumerate(TRANSACCIONES):
        tx_id = f"seed_{i:03d}"
        raw_struct = json.dumps(structure, sort_keys=True)

        emb_raw = qdrant.generar_embedding(raw)
        emb_struct = qdrant.generar_embedding(raw_struct)

        distancia = _distancia_coseno(emb_raw, emb_struct)
        distancias.append(distancia)

        payload = {
            "tx_id": tx_id,
            "raw": raw,
            "structure": raw_struct,
            "raw_distance_struct": round(distancia, 4),
            "tipo": "seed",
            "timestamp": "2026-06-17T19:00:00",
        }

        ok = qdrant.guardar_documento(tx_id, raw, payload, collection=COLECCION_TRANSACCIONES)
        if ok:
            guardadas += 1
            print(f"  [{i + 1}/10] {tx_id}: distance={distancia:.4f} {'⚠️' if distancia > 0.3 else '✅'}")
        else:
            print(f"  [{i + 1}/10] {tx_id}: FALLO al guardar")

    media = sum(distancias) / len(distancias) if distancias else 0
    print()
    print(f"Guardadas: {guardadas}/10 transacciones")
    print(f"Distancia media RAW vs STRUCT: {media:.4f}")
    print(f"Transacciones con alerta (dist > 0.3): {sum(1 for d in distancias if d > 0.3)}/{len(distancias)}")
    print()
    if guardadas > 0:
        print("Seed completado. Ahora /v2/interact debería devolver distance < 1.0")
    else:
        print("ERROR: No se guardó ninguna transacción")
        sys.exit(1)


if __name__ == "__main__":
    main()

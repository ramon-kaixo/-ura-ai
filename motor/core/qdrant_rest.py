"""Qdrant REST API helpers — fallback para QdrantClient cuando el cliente gRPC no está disponible.

Extraído de motor/core/qdrant_client.py para reducir tamaño del archivo.
"""

from __future__ import annotations

import hashlib
import logging

import httpx

COLECCION_INCIDENTES = "incidentes"

log = logging.getLogger("ura.qdrant.rest")


def guardar_rest(config, incidente: dict, build_payload) -> bool:
    try:
        payload = build_payload(incidente)
        point = {
            "id": int(hashlib.sha256(payload["timestamp_inicio"].encode()).hexdigest()[:15], 16) % (2**63),
            "vector": payload["impacto_memoria"],
            "payload": payload,
        }
        url = f"http://{config.qdrant_host}:{config.qdrant_port}/collections/{COLECCION_INCIDENTES}/points"
        r = httpx.put(url, json={"points": [point]}, timeout=5)
        return r.status_code in (200, 201)
    except Exception:
        log.exception("error guardar incidente REST")
        return False


def guardar_documentos_rest(config, puntos: list[dict], collection: str) -> int:
    try:
        url = f"http://{config.qdrant_host}:{config.qdrant_port}/collections/{collection}/points"
        r = httpx.put(url, json={"points": puntos}, timeout=10)
        return len(puntos) if r.status_code in (200, 201) else 0
    except Exception:
        log.exception("error guardar documentos batch REST")
        return 0


def buscar_similitud_rest(config, query_vector: list, collection: str, limit: int) -> list:
    try:
        url = f"http://{config.qdrant_host}:{config.qdrant_port}/collections/{collection}/points/search"
        r = httpx.post(url, json={"vector": query_vector, "limit": limit}, timeout=5)
        if r.status_code == 200:
            return [{"payload": p.get("payload", {}), "score": p.get("score", 0)} for p in r.json().get("result", [])]
    except Exception:
        log.warning("buscar_similitud_rest fallo: %s")
    return []


def eliminar_por_filtro_rest(config, filtro: dict, collection: str) -> bool:
    try:
        url = f"http://{config.qdrant_host}:{config.qdrant_port}/collections/{collection}/points/delete"
        must = [{"key": k, "match": {"value": v}} for k, v in filtro.items()]
        r = httpx.post(url, json={"filter": {"must": must}}, timeout=5)
        return r.status_code in (200, 201)
    except Exception:
        log.exception("error eliminar por filtro REST")
        return False

"""Almacen Qdrant: ideas -> embedding -> insert + busqueda."""

import logging
import threading
import uuid

import httpx
from qdrant_client import QdrantClient

from core.memoria.ficha import Idea
from motor.core.qdrant_client import URAQdrantClient

log = logging.getLogger("memoria.qdrant")

QDRANT_HOST = "127.0.0.1"
QDRANT_PORT = 6333
COLLECTION = "ideas"
EMBED_MODEL = "nomic-embed-text:latest"

_client: QdrantClient | None = None
_init_lock = threading.Lock()


def _get_client() -> QdrantClient:
    global _client  # noqa: PLW0603
    if _client is not None:
        return _client
    with _init_lock:
        if _client is None:
            _client = QdrantClient(QDRANT_HOST, port=QDRANT_PORT)
    return _client


async def _embed(texto: str) -> list[float]:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "http://127.0.0.1:11434/api/embeddings",
            json={"model": EMBED_MODEL, "prompt": texto},
        )
        resp.raise_for_status()
        return resp.json()["embedding"]


def _make_id(idea: Idea) -> str:
    base = idea.hash_origen or idea.idea[:40]
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{base}:{idea.idea}"))


async def almacenar_ideas(ideas: list[Idea]) -> int:
    if not ideas:
        return 0
    insertados = 0
    qdrant_async = URAQdrantClient()

    for idea in ideas:
        # Check existing via async REST
        must = [
            {"key": "hash_origen", "match": {"value": idea.hash_origen}},
            {"key": "version", "match": {"value": idea.version}},
        ]
        try:
            client = await qdrant_async._get_client()  # noqa: SLF001
            resp = await client.post(
                f"/collections/{COLLECTION}/points/search",
                json={"filter": {"must": must}, "limit": 1, "with_payload": False},
            )
            existing = resp.json().get("result", [])
            if existing:
                continue
        except Exception:
            log.exception("Error buscando punto existente en Qdrant")

        try:
            vec = await _embed(idea.texto_para_embedding())
        except Exception as e:
            log.exception(f"Embedding error: {e}")
            continue

        punto = {
            "id": _make_id(idea),
            "vector": vec,
            "payload": idea.to_payload(),
        }
        try:
            client = await qdrant_async._get_client()  # noqa: SLF001
            resp = await client.put(
                f"/collections/{COLLECTION}/points",
                json={"points": [punto]},
                params={"wait": "true"},
            )
            resp.raise_for_status()
            insertados += 1
        except Exception as e:
            log.exception(f"Qdrant upsert error: {e}")

    if insertados:
        log.info(f"Qdrant: {insertados}/{len(ideas)} ideas nuevas insertadas")
    return insertados


async def marcar_antiguas(fuente_url: str) -> int:
    qdrant_async = URAQdrantClient()
    marcadas = 0
    offset: int | None = None

    while True:
        params = {
            "filter": {
                "must": [
                    {"key": "fuente", "match": {"value": fuente_url}},
                    {"key": "vigente", "match": {"value": True}},
                ],
            },
            "limit": 50,
            "with_payload": True,
        }
        if offset is not None:
            params["offset"] = offset

        try:
            client = await qdrant_async._get_client()  # noqa: SLF001
            resp = await client.post(f"/collections/{COLLECTION}/points/scroll", json=params)
            resp.raise_for_status()
            data = resp.json()
            items = data.get("result", {}).get("points", [])
        except Exception as e:
            log.warning(f"Scroll falló: {e}")
            break

        for point in items:
            payload = point.get("payload", {})
            payload["vigente"] = False
            try:
                client = await qdrant_async._get_client()  # noqa: SLF001
                await client.put(
                    f"/collections/{COLLECTION}/points",
                    json={"points": [{"id": point["id"], "payload": payload}]},
                )
                marcadas += 1
            except Exception as e:
                log.warning(f"set_payload falló: {e}")

        if len(items) < 50:
            break
        offset = items[-1].get("id")

    if marcadas:
        log.info(f"Qdrant: {marcadas} ideas marcadas vigente=false para {fuente_url[:60]}")
    return marcadas


async def buscar_ideas(
    query: str,
    tema: str | None = None,
    tipo: str | None = None,
    coste: str | None = None,
    limit: int = 5,
) -> list[dict]:
    query_vec = await _embed(query)
    must = [{"key": "vigente", "match": {"value": True}}]
    if tema:
        must.append({"key": "tema", "match": {"value": tema}})
    if tipo:
        must.append({"key": "tipo", "match": {"value": tipo}})
    if coste:
        must.append({"key": "coste", "match": {"value": coste}})

    async with httpx.AsyncClient(timeout=15) as _ac_hc:
        resp = await _ac_hc.post(
            f"http://{QDRANT_HOST}:{QDRANT_PORT}/collections/{COLLECTION}/points/search",
            json={
                "vector": {"name": "texto", "vector": query_vec},
                "limit": limit,
                "filter": {"must": must},
                "with_payload": True,
            },
        )
        resp.raise_for_status()

        return [
            {
                "score": round(p.get("score", 0), 3),
                "id": p.get("id", ""),
                **(p.get("payload", {})),
            }
            for p in resp.json()["result"]
        ]


class MemoryPipelineStore:
    """Pipeline de memoria asíncrono. Usa URAQdrantClient con connection pooling (Hito 1.1.1)."""

    def __init__(self, qdrant_client: URAQdrantClient | None = None) -> None:
        self.qdrant = qdrant_client or URAQdrantClient()

    async def guardar_contexto_ingestado(self, coleccion: str, puntos: list) -> bool:
        """Inserta lotes de vectores en Qdrant sin bloquear el event-loop."""
        if not puntos:
            return False
        try:
            client = await self.qdrant._get_client()  # noqa: SLF001
            response = await client.put(
                f"/collections/{coleccion}/points",
                json={"points": puntos},
                params={"wait": "true"},
            )
            response.raise_for_status()
            log.info("MemoryPipelineStore: %d puntos indexados en '%s'", len(puntos), coleccion)
            return True
        except Exception as e:
            log.error("MemoryPipelineStore: fallo al guardar en Qdrant: %s", e, exc_info=True)  # noqa: G201
            return False

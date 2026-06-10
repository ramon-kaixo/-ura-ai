"""Almacen Qdrant: ideas -> embedding -> insert + busqueda."""
import logging
import uuid

import httpx
from qdrant_client import QdrantClient, models

from core.memoria.ficha import Idea

log = logging.getLogger("memoria.qdrant")

QDRANT_HOST = "127.0.0.1"
QDRANT_PORT = 6333
COLLECTION = "ideas"
EMBED_MODEL = "nomic-embed-text:latest"

_client: QdrantClient | None = None


def _get_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(QDRANT_HOST, port=QDRANT_PORT)
    return _client


def _embed(texto: str) -> list[float]:
    resp = httpx.post(
        "http://127.0.0.1:11434/api/embeddings",
        json={"model": EMBED_MODEL, "prompt": texto},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["embedding"]


def _make_id(idea: Idea) -> str:
    base = idea.hash_origen or idea.idea[:40]
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{base}:{idea.idea}"))


async def almacenar_ideas(ideas: list[Idea]) -> int:
    if not ideas:
        return 0

    client = _get_client()
    insertados = 0

    for idea in ideas:
        existing = client.query_points(
            COLLECTION,
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(key="hash_origen", match=models.MatchValue(value=idea.hash_origen)),
                    models.FieldCondition(key="version", match=models.MatchValue(value=idea.version)),
                ]
            ),
            limit=1,
            with_payload=False,
        )
        if existing.points:
            continue

        try:
            vec = _embed(idea.texto_para_embedding())
        except Exception as e:
            log.error(f"Embedding error: {e}")
            continue

        client.upsert(COLLECTION, [models.PointStruct(
            id=_make_id(idea),
            vector=vec,
            payload=idea.to_payload(),
        )])
        insertados += 1

    if insertados:
        log.info(f"Qdrant: {insertados}/{len(ideas)} ideas nuevas insertadas")
    return insertados


def buscar_ideas(
    query: str,
    tema: str | None = None,
    tipo: str | None = None,
    coste: str | None = None,
    limit: int = 5,
) -> list[dict]:
    client = _get_client()
    query_vec = _embed(query)

    filtros = [models.FieldCondition(key="vigente", match=models.MatchValue(value=True))]
    if tema:
        filtros.append(models.FieldCondition(key="tema", match=models.MatchValue(value=tema)))
    if tipo:
        filtros.append(models.FieldCondition(key="tipo", match=models.MatchValue(value=tipo)))
    if coste:
        filtros.append(models.FieldCondition(key="coste", match=models.MatchValue(value=coste)))

    results = client.query_points(COLLECTION, query=query_vec, limit=limit,
        query_filter=models.Filter(must=filtros))

    return [
        {
            "score": round(p.score, 3) if p.score else 0,
            "id": p.id,
            **p.payload,
        }
        for p in results.points
    ]

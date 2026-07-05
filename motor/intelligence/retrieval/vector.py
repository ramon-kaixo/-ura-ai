"""VectorRetriever — busca por similitud coseno en Qdrant."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from motor.core.qdrant_client import QdrantClient

log = logging.getLogger("ura.retrieval.vector")

COLECCION_SEMANTICA = "ura_docs_semantic"


class VectorRetriever:
    def __init__(self, qdrant_client: QdrantClient, collection: str = COLECCION_SEMANTICA) -> None:
        self._qc = qdrant_client
        self._collection = collection
        self._client = getattr(qdrant_client, "_cliente", None)

    def search(self, query: str, k: int = 10) -> list[dict[str, Any]]:
        start = time.monotonic()
        vector = self._qc.generar_embedding(query)
        emb_latency = (time.monotonic() - start) * 1000

        if self._client is None:
            return []

        qdrant_start = time.monotonic()
        hits = self._client.query_points(
            collection_name=self._collection,
            query=vector,
            limit=k,
            with_payload=True,
        )
        qdrant_latency = (time.monotonic() - qdrant_start) * 1000

        results = []
        for h in (hits.points if hits else []):
            payload = h.payload or {}
            doc_id = payload.get("source") or payload.get("id", str(h.id))
            results.append({
                "doc_id": doc_id,
                "score": h.score,
                "rank": len(results),
                "latency_ms": round(emb_latency + qdrant_latency, 2),
                "source": "vector",
                "payload": payload,
            })
        return results

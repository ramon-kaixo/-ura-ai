"""QdrantVectorStore — implementa VectorStore(Protocol) vía API HTTP directa.

Dependencia: httpx (ya disponible). Sin qdrant-client.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

import httpx

from knowledge.engine.vector_base import VectorItem, VectorResult

log = logging.getLogger("ura.knowledge.vector_qdrant")


def _point_id() -> str:
    """Genera un ID único para puntos Qdrant."""
    return uuid.uuid4().hex[:16]


class QdrantVectorStore:
    """Almacén vectorial usando Qdrant (HTTP directo).

    Args:
        collection: Nombre de la colección en Qdrant.
        host: Host del servidor Qdrant.
        port: Puerto REST del servidor Qdrant.
        vector_size: Dimensión de vectores. None = auto-detect.
        timeout: Timeout para requests HTTP.

    """

    def __init__(
        self,
        collection: str = "ura_assets",
        host: str = "localhost",
        port: int = 6333,
        vector_size: int | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._collection = collection
        self._vector_size = vector_size
        self._base_url = f"http://{host}:{port}"
        self._client = httpx.Client(base_url=self._base_url, timeout=timeout)
        self._degraded = False
        self._last_check: float = 0.0
        self._backoff: float = 1.0

    # ── Public API ─────────────────────────────────────────────────────────

    def search(
        self,
        query_vector: list[float],
        top_k: int = 10,
        filter: dict[str, Any] | None = None,  # noqa: A002
    ) -> list[VectorResult]:
        if not self.available:
            return []
        if not query_vector:
            return []
        try:
            body: dict[str, Any] = {
                "vector": query_vector,
                "limit": top_k,
                "with_payload": True,
            }
            if filter:
                body["filter"] = self._translate_filter(filter)
            resp = self._client.post(
                f"/collections/{self._collection}/points/search",
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()
            results = data.get("result", [])
            return [
                VectorResult(
                    asset_id=point.get("id", ""),
                    score=point["score"],
                    metadata=point.get("payload", {}),
                )
                for point in results
            ]
        except httpx.HTTPError as exc:
            log.warning("Qdrant search failed: %s", exc)
            self._degraded = True
            return []

    def upsert(self, items: list[VectorItem]) -> int:
        if not items:
            return 0
        if not self.available:
            return 0
        try:
            self._ensure_collection(items[0].vector)
            points = [
                {
                    "id": item.asset_id,
                    "vector": item.vector,
                    "payload": {
                        "asset_id": item.asset_id,
                        "text_preview": item.text_preview,
                    },
                }
                for item in items
            ]
            resp = self._client.put(
                f"/collections/{self._collection}/points",
                json={"points": points},
            )
            resp.raise_for_status()
            return len(points)
        except httpx.HTTPError as exc:
            log.warning("Qdrant upsert failed: %s", exc)
            self._degraded = True
            return 0

    def delete(self, asset_ids: list[str]) -> int:
        if not asset_ids:
            return 0
        if not self.available:
            return 0
        try:
            resp = self._client.post(
                f"/collections/{self._collection}/points/delete",
                json={
                    "filter": {
                        "must": [
                            {"has_id": asset_ids},
                        ],
                    },
                },
            )
            resp.raise_for_status()
            return len(asset_ids)
        except httpx.HTTPError as exc:
            log.warning("Qdrant delete failed: %s", exc)
            self._degraded = True
            return 0

    def count(self) -> int:
        if not self.available:
            return 0
        try:
            resp = self._client.post(
                f"/collections/{self._collection}/points/count",
                json={},
            )
            resp.raise_for_status()
            data = resp.json()
            result = data.get("result", {})
            return result.get("count", 0)
        except httpx.HTTPError as exc:
            log.warning("Qdrant count failed: %s", exc)
            self._degraded = True
            return 0

    def list_ids(
        self,
        limit: int = 100,
        offset: str | None = None,
        timeout: float | None = None,
    ) -> tuple[list[str], str | None]:
        """Enumera asset_ids vía scroll API de Qdrant.

        Args:
            limit: Máximo de IDs por página (default 100).
            offset: Cursor de paginación (UUID hex). None = primera página.
            timeout: Timeout en segundos para la llamada scroll.
                     None = usa el timeout por defecto del cliente HTTP.

        Returns:
            Tuple de (ids, next_offset). next_offset=None = última página.

        """
        if not self.available:
            return [], None
        try:
            body: dict[str, Any] = {
                "limit": limit,
                "with_payload": False,
                "with_vector": False,
            }
            if offset is not None:
                body["offset"] = offset
            resp = self._client.post(
                f"/collections/{self._collection}/points/scroll",
                json=body,
                timeout=timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            result = data.get("result", {})
            points = result.get("points", [])
            next_offset = result.get("next_page_offset")
            ids = [p["id"] for p in points]
            return ids, next_offset
        except httpx.HTTPError as exc:
            log.warning("Qdrant list_ids failed: %s", exc)
            self._degraded = True
            return [], None

    @property
    def available(self) -> bool:
        """O(1), sin side-effects. Refleja último estado conocido."""
        return not self._degraded

    def check_available(self) -> bool:
        """Verifica disponibilidad en tiempo real con exponential backoff.

        Side-effects: muta _degraded y _backoff.
        """
        if not self._degraded:
            return True
        now = time.monotonic()
        if now - self._last_check < self._backoff:
            return False
        self._last_check = now
        try:
            resp = self._client.get("/health")
            if resp.status_code == 200:
                self._degraded = False
                self._backoff = 1.0
                return True
            self._degraded = True
            self._backoff = min(self._backoff * 2, 60.0)
            return False
        except httpx.HTTPError:
            self._backoff = min(self._backoff * 2, 60.0)
            return False

    # ── Internals ──────────────────────────────────────────────────────────

    def _ensure_collection(self, vector: list[float]) -> None:
        """Crea la colección si no existe."""
        vsize = self._vector_size or len(vector)
        try:
            resp = self._client.put(
                f"/collections/{self._collection}",
                json={
                    "vectors": {
                        "size": vsize,
                        "distance": "Cosine",
                    },
                },
            )
            # 200 = created, 409 = already exists (acceptable)
            if resp.status_code not in (200, 409):
                resp.raise_for_status()
        except httpx.HTTPError as exc:
            log.warning("Qdrant ensure collection failed: %s", exc)
            raise

    @staticmethod
    def _translate_filter(filter: dict[str, Any]) -> dict[str, Any]:  # noqa: A002
        """Traduce un filter plano al formato Qdrant.

        Ej: {"asset_type": "pdf"} → {"must": [{"key": "asset_type", "match": {"value": "pdf"}}]}
        """
        must = []
        for key, value in filter.items():
            must.append({"key": key, "match": {"value": value}})
        return {"must": must}

    def close(self) -> None:
        """Cierra el cliente HTTP. Llamar al finalizar."""
        self._client.close()

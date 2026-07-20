"""VectorAugmentedRetriever — wrapper que compone GraphRetriever + Embedder + VectorStore + RRF.

No modifica ninguna clase existente. Sin backend vectorial (embedder=None o
vector_store=None) se comporta como GraphRetriever puro.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from knowledge.engine.vector_base import VectorItem

if TYPE_CHECKING:
    from collections.abc import Sequence

    from knowledge.engine.asset_store import AssetStore
    from knowledge.engine.graphrag import GraphRetriever
    from knowledge.engine.models import KnowledgeAsset
    from knowledge.engine.ontology.internal import AssetType
    from knowledge.engine.vector_base import Embedder, VectorResult, VectorStore

logger = logging.getLogger(__name__)


class VectorAugmentedRetriever:
    """Wrapper que compone GraphRetriever + AssetStore + Embedder + VectorStore + RRF.

    No modifica ninguna clase existente. Delega en GraphRetriever para
    la búsqueda heurística y en Embedder/VectorStore para la semántica.
    AssetStore es necesaria para resolver asset_ids a KnowledgeAsset.
    """

    def __init__(
        self,
        graph_retriever: GraphRetriever,
        asset_store: AssetStore,
        embedder: Embedder | None = None,
        vector_store: VectorStore | None = None,
        rrf_k: int = 60,
    ) -> None:
        self._graph = graph_retriever
        self._asset_store = asset_store
        self._embedder = embedder
        self._vector_store = vector_store
        self._rrf_k = rrf_k

    def retrieve_assets(
        self,
        query: str,
        limit: int = 10,
        *,
        use_vector: bool = False,
        asset_type: AssetType | None = None,
    ) -> list[KnowledgeAsset]:
        """Recupera assets combinando búsqueda heurística y vectorial.

        La búsqueda heurística siempre se ejecuta. La búsqueda vectorial
        solo se ejecuta si use_vector=True y embedder+vector_store están
        disponibles. Los resultados se fusionan con Reciprocal Rank Fusion.

        Degradación graceful: si la búsqueda vectorial falla (embedder
        caído, timeout, etc.), se retorna solo la búsqueda heurística.
        """
        heuristic = self._graph.retrieve_assets(query, limit=limit, asset_type=asset_type)

        vector: list[VectorResult] = []
        if use_vector and self._vector_available():
            try:
                query_vec = self._embedder.embed_query(query)
                if query_vec:
                    vector = self._vector_store.search(query_vec, top_k=limit)
            except Exception:
                logger.warning("Vector search failed, using heuristic only", exc_info=True)

        return self._resolve_rrf(heuristic, vector, limit)

    def _vector_available(self) -> bool:
        return (
            self._embedder is not None
            and self._embedder.available
            and self._vector_store is not None
            and self._vector_store.available
        )

    def _resolve_rrf(
        self,
        heuristic: Sequence[Any],
        vector: Sequence[VectorResult],
        limit: int,
    ) -> list[KnowledgeAsset]:
        """Reciprocal Rank Fusion + resolución a KnowledgeAsset.

        Los elementos de *heuristic* y *vector* deben tener un atributo
        ``asset_id`` (ej: RetrievalResult, VectorResult).
        """
        scores: dict[str, float] = {}

        for rank, result in enumerate(heuristic):
            aid = result.asset_id  # type: ignore[union-attr]
            scores[aid] = 1.0 / (self._rrf_k + rank)

        for rank, result in enumerate(vector):
            aid = result.asset_id
            if aid in scores:
                scores[aid] += 1.0 / (self._rrf_k + rank)
            else:
                scores[aid] = 1.0 / (self._rrf_k + rank)

        ranked = sorted(scores.items(), key=lambda x: -x[1])

        resolved: list[KnowledgeAsset] = []
        for aid, _ in ranked[:limit]:
            asset = self._asset_store.get_asset(aid)
            if asset is not None:
                resolved.append(asset)

        return resolved

    def reconcile(self, dry_run: bool = True, batch_size: int = 100) -> dict[str, int]:  # noqa: C901
        """Reconcilia AssetStore con VectorStore.

        Para cada asset en AssetStore, verifica si existe en VectorStore.
        Si falta, lo embedde y upsert. Si sobra (huérfano), lo elimina.

        Args:
            dry_run: Si True, solo reporta sin modificar nada.
            batch_size: Assets por iteración.

        Returns:
            Dict con stats: to_upsert, to_delete, upserted, deleted.

        """
        stats: dict[str, int] = {"to_upsert": 0, "to_delete": 0, "upserted": 0, "deleted": 0}

        if self._embedder is None or self._vector_store is None:
            return stats

        # Colectar assets
        offset = 0
        all_asset_ids: dict[str, KnowledgeAsset] = {}
        while True:
            try:
                batch = self._asset_store.list_assets(limit=batch_size, offset=offset)
            except Exception:
                logger.warning("Failed to list assets at offset %d, stopping reconcile", offset)
                break
            if not batch:
                break
            for a in batch:
                all_asset_ids[a.asset_id] = a
            offset += len(batch)

        ids_in_store = self._get_vector_ids()
        ids_in_assets = set(all_asset_ids)

        upsert_candidates = ids_in_assets - ids_in_store
        delete_candidates = ids_in_store - ids_in_assets

        stats["to_upsert"] = len(upsert_candidates)
        stats["to_delete"] = len(delete_candidates)

        if dry_run:
            return stats

        # Upsert assets faltantes
        text_previews: list[str] = []
        assets_to_embed: list[KnowledgeAsset] = []
        for aid in sorted(upsert_candidates):
            asset = all_asset_ids[aid]
            text_previews.append(asset.metadata.get("text_preview", asset.metadata.get("title", "")))
            assets_to_embed.append(asset)

            if len(assets_to_embed) >= batch_size:
                self._upsert_batch(assets_to_embed, text_previews, stats)
                text_previews = []
                assets_to_embed = []

        if assets_to_embed:
            self._upsert_batch(assets_to_embed, text_previews, stats)

        # Eliminar vectores huérfanos
        orphan_ids = sorted(delete_candidates)
        for i in range(0, len(orphan_ids), batch_size):
            batch = orphan_ids[i : i + batch_size]
            deleted = self._vector_store.delete(batch)
            stats["deleted"] += deleted

        return stats

    def _get_vector_ids(self) -> set[str]:
        """Obtiene IDs de todos los vectores en el store mediante list_ids()."""
        ids: set[str] = set()
        seen_offsets: set[str] = set()
        try:
            next_offset: str | None = None
            while True:
                batch, next_offset = self._vector_store.list_ids(
                    limit=100,
                    offset=next_offset,
                )
                if not batch:
                    break
                ids.update(batch)
                if not next_offset:
                    break
                if next_offset in seen_offsets:
                    logger.warning(
                        "Duplicate next_offset=%s in _get_vector_ids, breaking loop to prevent infinite pagination",
                        next_offset,
                    )
                    break
                seen_offsets.add(next_offset)
        except Exception as exc:
            logger.warning("Error getting vector IDs: %s, returning empty set", exc)
            return set()
        return ids

    def _upsert_batch(self, assets: list[KnowledgeAsset], text_previews: list[str], stats: dict[str, int]) -> None:
        """Embedde y upsert un batch de assets."""
        try:
            vectors = self._embedder.embed(text_previews)
        except Exception:
            logger.warning("Embedding raised exception for batch, skipping %d assets", len(assets))
            return
        if not vectors:
            logger.warning("Embedding failed for batch, skipping %d assets", len(assets))
            return
        items = [
            VectorItem(
                asset_id=a.asset_id,
                vector=v,
                text_preview=t,
            )
            for a, v, t in zip(assets, vectors, text_previews, strict=False)
            if v
        ]
        if items:
            upserted = self._vector_store.upsert(items)
            stats["upserted"] += upserted

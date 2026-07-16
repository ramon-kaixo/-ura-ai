"""GraphRAG — motor de recuperación de contexto para el Knowledge Graph.

NO contiene integración con LLMs.
NO contiene embeddings.
NO contiene vector search.

Es únicamente un motor de recuperación determinista que consulta los 4 stores
(Asset, Memory, Lineage, Governance) y construye un ContextBundle.

Preparado para que en el futuro un LLM consuma este contexto.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from knowledge.engine.ontology.internal import AssetType, KnowledgeAsset

log = logging.getLogger("ura.knowledge.graphrag")


@dataclass(frozen=True)
class ContextBundle:
    """Contexto completo recuperado del grafo de conocimiento.

    Este objeto es la entrada para un LLM (GraphRAG).
    Es completamente determinista.
    """

    query: str
    assets: list[dict[str, Any]] = field(default_factory=list)
    memories: list[dict[str, Any]] = field(default_factory=list)
    lineage: list[dict[str, Any]] = field(default_factory=list)
    governance: list[dict[str, Any]] = field(default_factory=list)
    neighbors: list[dict[str, Any]] = field(default_factory=list)
    total_duration_ms: float = 0.0
    asset_count: int = 0
    memory_count: int = 0
    lineage_count: int = 0
    governance_count: int = 0
    neighbor_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "assets": self.assets,
            "memories": self.memories,
            "lineage": self.lineage,
            "governance": self.governance,
            "neighbors": self.neighbors,
            "stats": {
                "assets": self.asset_count,
                "memories": self.memory_count,
                "lineage": self.lineage_count,
                "governance": self.governance_count,
                "neighbors": self.neighbor_count,
                "duration_ms": self.total_duration_ms,
            },
        }


@dataclass
class RetrievalResult:
    """Resultado de una recuperación individual."""

    asset_id: str
    score: float
    title: str = ""
    kind: str = ""
    snippet: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


# ── Ranking heurístico ─────────────────────────────────────────────────────


_RANKING_WEIGHTS = {
    "title_match": 0.4,
    "tag_match": 0.2,
    "recency": 0.15,
    "quality": 0.15,
    "depth": 0.1,
}

_DEFAULT_QUALITY = 0.5


def _compute_score(query: str, asset: KnowledgeAsset | None = None, memory: Any = None, max_days: int = 365) -> float:
    """Score heurístico 0.0-1.0. Sin IA."""
    score = 0.0
    query_lower = query.lower()

    # Title match
    title = ""
    if asset:
        title = asset.metadata.get("title", "")
    elif memory:
        title = getattr(memory, "title", "")
    if query_lower in title.lower():
        score += _RANKING_WEIGHTS["title_match"]

    # Recency
    if asset:
        updated = asset.updated_at
    elif memory:
        updated = getattr(memory, "updated_at", "") or getattr(memory, "created_at", "")
    else:
        updated = ""
    if updated:
        try:
            from datetime import UTC, datetime
            from dateutil import parser

            dt = parser.parse(updated)
            days_ago = (datetime.now(UTC) - dt).days
            if days_ago < max_days:
                recency = 1.0 - (days_ago / max_days)
                score += _RANKING_WEIGHTS["recency"] * recency
        except Exception:
            pass

    # Quality
    if asset:
        q = asset.quality
    else:
        q = _DEFAULT_QUALITY
    score += _RANKING_WEIGHTS["quality"] * q

    return min(score, 1.0)


# ── GraphRetriever Protocol ───────────────────────────────────────────────


class GraphRetriever(Protocol):
    """Contrato para recuperadores de contexto del Knowledge Graph."""

    def retrieve_assets(
        self, query: str, limit: int = 10, asset_type: AssetType | None = None
    ) -> list[RetrievalResult]: ...
    def retrieve_memory(self, query: str, limit: int = 10, kind: str | None = None) -> list[RetrievalResult]: ...
    def retrieve_lineage(self, asset_id: str) -> list[dict[str, Any]]: ...
    def retrieve_governance(self, asset_id: str) -> list[dict[str, Any]]: ...
    def retrieve_neighbors(self, asset_id: str, depth: int = 2, max_nodes: int = 100) -> list[dict[str, Any]]: ...
    def build_context(
        self,
        query: str,
        max_assets: int = 10,
        max_memories: int = 5,
        include_lineage: bool = True,
        include_governance: bool = True,
        neighbor_depth: int = 0,
    ) -> ContextBundle: ...


# ── SQLiteGraphRetriever ───────────────────────────────────────────────────


class SQLiteGraphRetriever:
    """Implementación SQLite de GraphRetriever.

    Consume exclusivamente los Stores existentes.
    No accede directamente a SQLite.
    """

    def __init__(self, db_path: Path):
        self._db_path = db_path
        self._asset_store: Any = None
        self._memory_store: Any = None
        self._lineage_store: Any = None
        self._governance_store: Any = None

    def _get_asset_store(self):
        if self._asset_store is None:
            from knowledge.engine.asset_store import SQLiteAssetStore

            self._asset_store = SQLiteAssetStore(self._db_path)
        return self._asset_store

    def _get_memory_store(self):
        if self._memory_store is None:
            from knowledge.engine.memory_store import SQLiteMemoryStore

            self._memory_store = SQLiteMemoryStore(self._db_path)
        return self._memory_store

    def _get_lineage_store(self):
        if self._lineage_store is None:
            from knowledge.engine.lineage_store import SQLiteLineageStore

            self._lineage_store = SQLiteLineageStore(self._db_path)
        return self._lineage_store

    def _get_governance_store(self):
        if self._governance_store is None:
            from knowledge.engine.governance_store import SQLiteGovernanceStore

            self._governance_store = SQLiteGovernanceStore(self._db_path)
        return self._governance_store

    def retrieve_assets(
        self, query: str, limit: int = 10, asset_type: AssetType | None = None
    ) -> list[RetrievalResult]:
        """Recupera assets relevantes para una consulta.

        Usa search_assets() (FTS5) con fallback a LIKE. Reordena por score heurístico.
        """
        store = self._get_asset_store()
        assets = store.search_assets(query=query, limit=limit * 3, asset_type=asset_type)

        results: list[RetrievalResult] = []
        for a in assets:
            score = _compute_score(query, asset=a)
            title = a.metadata.get("title", "")
            results.append(
                RetrievalResult(
                    asset_id=a.asset_id,
                    score=score,
                    title=title,
                    kind=a.asset_type.value,
                    snippet=a.metadata.get("content_sha256", "")[:64],
                )
            )

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    def retrieve_memory(self, query: str, limit: int = 10, kind: str | None = None) -> list[RetrievalResult]:
        """Recupera registros de memoria relevantes."""
        store = self._get_memory_store()
        records = store.search(query, kind=kind, limit=limit * 2)

        results: list[RetrievalResult] = []
        for r in records:
            score = _compute_score(query, memory=r)
            results.append(
                RetrievalResult(
                    asset_id=r.memory_id,
                    score=score,
                    title=r.title,
                    kind=r.kind,
                    snippet=r.content[:200],
                    metadata={"tags": list(r.tags), "related_assets": list(r.related_assets)},
                )
            )

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    def retrieve_lineage(self, asset_id: str) -> list[dict[str, Any]]:
        """Recupera el lineage de un asset."""
        store = self._get_lineage_store()
        up = store.get_upstream(asset_id)
        down = store.get_downstream(asset_id)
        events = store.get_lineage(asset_id)
        return [
            {
                "asset_id": asset_id,
                "upstream": up,
                "downstream": down,
                "events": len(events),
            }
        ]

    def retrieve_governance(self, asset_id: str) -> list[dict[str, Any]]:
        """Recupera políticas de gobernanza de un asset."""
        store = self._get_governance_store()
        policies = store.get_policies(asset_id)
        return [dict(p) for p in policies]

    def retrieve_neighbors(self, asset_id: str, depth: int = 2, max_nodes: int = 100) -> list[dict[str, Any]]:
        """Recupera vecinos en el grafo hasta *depth* niveles.

        Usa BFS con detección de ciclos (visited set).
        Retorna lista de {"asset_id", "relation", "depth"}.
        """
        from collections import deque

        store = self._get_lineage_store()
        visited: set[str] = {asset_id}
        queue: deque = deque([(asset_id, 0)])
        neighbors: list[dict[str, Any]] = []

        while queue and len(neighbors) < max_nodes:
            current, d = queue.popleft()
            if d >= depth:
                continue

            # Obtener vecinos (upstream + downstream)
            up = store.get_upstream(current)
            down = store.get_downstream(current)

            for nid in up:
                if nid not in visited:
                    visited.add(nid)
                    neighbors.append({"asset_id": nid, "relation": "upstream", "depth": d + 1})
                    if len(neighbors) >= max_nodes:
                        break
                    queue.append((nid, d + 1))

            for nid in down:
                if nid not in visited:
                    visited.add(nid)
                    neighbors.append({"asset_id": nid, "relation": "downstream", "depth": d + 1})
                    if len(neighbors) >= max_nodes:
                        break
                    queue.append((nid, d + 1))

        return neighbors

    def build_context(
        self,
        query: str,
        max_assets: int = 10,
        max_memories: int = 5,
        include_lineage: bool = True,
        include_governance: bool = True,
        neighbor_depth: int = 0,
    ) -> ContextBundle:
        """Construye un ContextBundle completo para una consulta.

        Flujo:
          1. Recuperar assets relevantes
          2. Recuperar memorias relevantes
          3. Para cada asset top-N, recuperar lineage y governance
          4. Ensamblar ContextBundle determinista
        """
        t0 = time.monotonic()

        assets = self.retrieve_assets(query, limit=max_assets)
        memories = self.retrieve_memory(query, limit=max_memories)

        lineage = []
        governance = []
        neighbors = []
        top_ids = [a.asset_id for a in assets[:3]]
        for aid in top_ids:
            if include_lineage:
                lineage.extend(self.retrieve_lineage(aid))
            if include_governance:
                governance.extend(self.retrieve_governance(aid))
            if neighbor_depth > 0:
                n = self.retrieve_neighbors(aid, depth=neighbor_depth, max_nodes=50)
                # Dedup por asset_id
                seen = set()
                for entry in n:
                    if entry["asset_id"] not in seen:
                        seen.add(entry["asset_id"])
                        neighbors.append(entry)

        duration = (time.monotonic() - t0) * 1000

        return ContextBundle(
            query=query,
            assets=[
                {"asset_id": a.asset_id, "score": a.score, "title": a.title, "kind": a.kind, "snippet": a.snippet}
                for a in assets
            ],
            memories=[
                {
                    "memory_id": m.asset_id,
                    "score": m.score,
                    "title": m.title,
                    "kind": m.kind,
                    "snippet": m.snippet,
                    "metadata": m.metadata,
                }
                for m in memories
            ],
            lineage=lineage,
            governance=governance,
            neighbors=neighbors,
            total_duration_ms=duration,
            asset_count=len(assets),
            memory_count=len(memories),
            lineage_count=len(lineage),
            governance_count=len(governance),
            neighbor_count=len(neighbors),
        )

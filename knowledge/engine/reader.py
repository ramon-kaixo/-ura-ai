"""KnowledgeReader — consultas al grafo de conocimiento.

Solo lectura. Nunca escribe.
Toda la lógica trabaja sobre models.py, nunca sobre SQL directamente.
"""

from __future__ import annotations

import contextlib
import json
import weakref
from collections import OrderedDict
from pathlib import Path
from typing import TYPE_CHECKING, Any

from knowledge.engine.audit import get_audit
from knowledge.engine.models import (
    HYBRID_RRF_K,
    Document,
    Frontmatter,
    GraphNode,
    Relation,
    SearchResult,
)
from knowledge.engine.qdrant_sync import get_pending_delete_ids, search_semantic

if TYPE_CHECKING:
    import sqlite3

_READER_POOL: dict[str, Any] = {}  # db_path → ReadConnectionPool
_READER_POOL_MAX = 10  # máx pools distintos antes de evictar el más antiguo


def _get_conn(db_path: Path) -> sqlite3.Connection:
    """Obtiene conexión del pool de lectura. Crea pool si no existe."""
    global _READER_POOL
    spath = str(db_path)
    if spath not in _READER_POOL:
        from knowledge.engine.connection_pool import ReadConnectionPool

        # Si excedemos el límite, cerrar el pool más antiguo
        if len(_READER_POOL) >= _READER_POOL_MAX:
            oldest_key = next(iter(_READER_POOL))
            oldest_pool = _READER_POOL.pop(oldest_key)
            oldest_pool.close_all()

        _READER_POOL[spath] = ReadConnectionPool(db_path, max_connections=5)
    return _READER_POOL[spath].acquire()


def _release_conn(conn: sqlite3.Connection, db_path: Path) -> None:
    """Devuelve conexión al pool."""
    global _READER_POOL
    spath = str(db_path)
    if spath in _READER_POOL:
        _READER_POOL[spath].release(conn)
    else:
        conn.close()


def clear_all_connection_pools() -> None:
    """Cierra todas las conexiones de todos los pools."""
    global _READER_POOL
    for pool in _READER_POOL.values():
        pool.close_all()
    _READER_POOL.clear()


_READER_INSTANCES: weakref.WeakSet[KnowledgeReader] = weakref.WeakSet()


def clear_all_caches() -> None:
    """Invalida todas las cachés de todos los KnowledgeReader activos.

    Llamado por el writer tras apply_compile() para asegurar
    que el reader nunca sirva datos obsoletos.
    """
    for reader in list(_READER_INSTANCES):
        reader.clear_cache()


def _row_to_document(row: sqlite3.Row) -> Document:
    fm = Frontmatter.from_dict(json.loads(row["frontmatter"]))
    semantic_raw = row["semantic"]
    return Document(
        doc_id=row["id"],
        doc_type=row["type"],
        path=row["path"],
        content_sha256=row["content_sha256"],
        frontmatter=fm,
        body=row["body"] or "",
        semantic=json.loads(semantic_raw) if semantic_raw else {},
        quality=row["quality"] or 0.0,
        confidence=row["confidence"] or 0.0,
        embed_hash=row["embed_hash"],
        updated_at=row["updated_at"],
    )


class KnowledgeReader:
    """Solo lectura. WAL mode. Nunca escribe."""

    _CACHE_MAXSIZE = 100

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._doc_cache: OrderedDict[str, Document] = OrderedDict()
        _READER_INSTANCES.add(self)

    def get_document(self, doc_id: str) -> Document | None:
        cached = self._doc_cache.get(doc_id)
        if cached is not None:
            self._doc_cache.move_to_end(doc_id)
            return cached
        conn = _get_conn(self._db_path)
        try:
            row = conn.execute("SELECT * FROM kg_nodes WHERE id = ?", (doc_id,)).fetchone()
            if row is None:
                return None
            doc = _row_to_document(row)
            self._cache_document(doc_id, doc)
            return doc
        finally:
            _release_conn(conn, self._db_path)

    def _cache_document(self, doc_id: str, doc: Document) -> None:
        if len(self._doc_cache) >= self._CACHE_MAXSIZE:
            self._doc_cache.popitem(last=False)
        self._doc_cache[doc_id] = doc

    def clear_cache(self) -> None:
        self._doc_cache.clear()

    def search(
        self,
        query: str,
        mode: str = "lexical",
        filters: dict[str, Any] | None = None,
        limit: int = 10,
    ) -> list[SearchResult]:
        if mode == "lexical":
            results = self._search_lexical(query, filters, limit)
        elif mode == "hybrid":
            results = self._search_hybrid(query, filters, limit)
        else:
            raise ValueError(f"Modo de búsqueda no soportado: {mode!r}")
        with contextlib.suppress(Exception):
            get_audit().log_read(query=query, docs=len(results))
        return results

    def _search_lexical(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 10,
    ) -> list[SearchResult]:
        conn = _get_conn(self._db_path)
        try:
            sql = (
                "SELECT n.id, n.type, n.path, n.frontmatter, n.body, "
                "       rank "
                "FROM kg_nodes_fts f "
                "JOIN kg_nodes n ON n.id = f.id "
                "WHERE kg_nodes_fts MATCH ? "
            )
            params: list[Any] = [query]

            if filters:
                if "type" in filters:
                    sql += "AND n.type = ? "
                    params.append(filters["type"])
                if "path_prefix" in filters:
                    sql += "AND n.path LIKE ? "
                    params.append(filters["path_prefix"] + "%")

            sql += "ORDER BY rank LIMIT ?"
            params.append(limit)

            rows = conn.execute(sql, params).fetchall()
            results: list[SearchResult] = []
            for row in rows:
                fm = Frontmatter.from_dict(json.loads(row["frontmatter"]))
                results.append(
                    SearchResult(
                        doc_id=row["id"],
                        score=float(row["rank"]) if row["rank"] is not None else 0.0,
                        title=fm.title,
                        snippet=_make_snippet(row["body"], query),
                        doc_type=row["type"],
                    )
                )
            return results
        finally:
            _release_conn(conn, self._db_path)

    def _search_hybrid(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 10,
    ) -> list[SearchResult]:
        semantic_raw = search_semantic(query, top_k=limit * 2)
        if not semantic_raw:
            return self._search_lexical(query, filters, limit)

        pending_delete = set(get_pending_delete_ids(self._db_path))

        rrf_k = HYBRID_RRF_K
        rrf_scores: dict[str, dict[str, Any]] = {}

        for pos, hit in enumerate(semantic_raw):
            did = hit["doc_id"]
            if did in pending_delete:
                continue
            if did not in rrf_scores:
                rrf_scores[did] = {
                    "rrf": 0.0,
                    "text": hit["text"],
                    "title": hit["title"],
                    "doc_type": hit.get("doc_type", ""),
                }
            rrf_scores[did]["rrf"] += 1.0 / (rrf_k + pos + 1)

        lexical = self._search_lexical(query, filters, limit)
        for pos, lex in enumerate(lexical):
            if lex.doc_id in pending_delete:
                continue
            if lex.doc_id not in rrf_scores:
                rrf_scores[lex.doc_id] = {
                    "rrf": 0.0,
                    "text": lex.snippet,
                    "title": lex.title,
                    "doc_type": lex.doc_type,
                }
            rrf_scores[lex.doc_id]["rrf"] += 1.0 / (rrf_k + pos + 1)

        ranked = sorted(rrf_scores.items(), key=lambda x: x[1]["rrf"], reverse=True)
        return [
            SearchResult(
                doc_id=did,
                score=data["rrf"],
                title=data["title"],
                snippet=data["text"][:200],
                doc_type=data["doc_type"],
            )
            for did, data in ranked[:limit]
        ]

    def related(
        self,
        doc_id: str,
        relation: str | None = None,
        depth: int = 2,
    ) -> list[Relation]:
        conn = _get_conn(self._db_path)
        try:
            visited: set[str] = set()
            results: list[Relation] = []
            self._traverse_relations(conn, doc_id, relation, depth, visited, results)
            return results
        finally:
            _release_conn(conn, self._db_path)

    def _traverse_relations(
        self,
        conn: sqlite3.Connection,
        node_id: str,
        relation: str | None,
        depth: int,
        visited: set[str],
        results: list[Relation],
    ) -> None:
        if depth <= 0 or node_id in visited:
            return
        visited.add(node_id)

        sql = "SELECT src, dst, relation, metadata FROM kg_edges WHERE src = ?"
        params: list[Any] = [node_id]
        if relation:
            sql += " AND relation = ?"
            params.append(relation)

        rows = conn.execute(sql, params).fetchall()
        for row in rows:
            rel = Relation(
                src=row["src"],
                dst=row["dst"],
                relation=row["relation"],
                metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            )
            results.append(rel)
            self._traverse_relations(conn, row["dst"], relation, depth - 1, visited, results)

    def graph(self, root: str | None = None, depth: int = 2) -> list[GraphNode]:
        conn = _get_conn(self._db_path)
        try:
            if root is None:
                rows = conn.execute("SELECT id, type, path, frontmatter FROM kg_nodes LIMIT 100").fetchall()
                return [self._row_to_graphnode(r, conn) for r in rows]

            visited: set[str] = set()
            nodes: list[GraphNode] = []
            self._collect_subgraph(conn, root, depth, visited, nodes)
            return nodes
        finally:
            _release_conn(conn, self._db_path)

    def _row_to_graphnode(self, row: sqlite3.Row, conn: sqlite3.Connection) -> GraphNode:
        fm = Frontmatter.from_dict(json.loads(row["frontmatter"]))
        edges = conn.execute(
            "SELECT src, dst, relation, metadata FROM kg_edges WHERE src = ?",
            (row["id"],),
        ).fetchall()
        rels = tuple(
            Relation(
                src=e["src"],
                dst=e["dst"],
                relation=e["relation"],
                metadata=json.loads(e["metadata"]) if e["metadata"] else {},
            )
            for e in edges
        )
        return GraphNode(
            doc_id=row["id"],
            doc_type=row["type"],
            title=fm.title,
            path=row["path"],
            relations=rels,
        )

    def _collect_subgraph(
        self,
        conn: sqlite3.Connection,
        node_id: str,
        depth: int,
        visited: set[str],
        nodes: list[GraphNode],
    ) -> None:
        if depth <= 0 or node_id in visited:
            return
        visited.add(node_id)
        row = conn.execute(
            "SELECT id, type, path, frontmatter FROM kg_nodes WHERE id = ?",
            (node_id,),
        ).fetchone()
        if row is None:
            return
        nodes.append(self._row_to_graphnode(row, conn))
        edges = conn.execute("SELECT dst FROM kg_edges WHERE src = ?", (node_id,)).fetchall()
        for e in edges:
            self._collect_subgraph(conn, e["dst"], depth - 1, visited, nodes)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_snippet(body: str, query: str, context_chars: int = 100) -> str:
    """Extrae un snippet alrededor de la primera ocurrencia del query."""
    if not body or not query:
        return (body or "")[: context_chars * 2]
    idx = body.lower().find(query.lower().split()[0]) if " " in query else body.lower().find(query.lower())
    if idx == -1:
        return body[: context_chars * 2]
    start = max(0, idx - context_chars)
    end = min(len(body), idx + context_chars)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(body) else ""
    return f"{prefix}{body[start:end]}{suffix}"

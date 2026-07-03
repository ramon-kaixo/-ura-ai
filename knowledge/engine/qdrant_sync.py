"""QdrantSync — sincroniza Chunks con Qdrant para búsqueda semántica.

Dependencia externa opcional: motor.core.qdrant_client.QdrantClient.
Si Qdrant no está disponible, las operaciones fallan silenciosamente
(graceful degradation — el compile sigue siendo exitoso).

Tracking: op_vector_sync registra operaciones fallidas para reintento.
Si attempts >= MAX_SYNC_ATTEMPTS (10) → dead_letter (no reintentar más).
"""

from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from knowledge.engine.chunker import chunk_document
from knowledge.engine.connection import open_db
from knowledge.engine.models import MAX_SYNC_ATTEMPTS

if TYPE_CHECKING:
    from pathlib import Path

    from knowledge.engine.models import Document

log = logging.getLogger("ura.knowledge.qdrant_sync")

_EMBEDDING_MODEL = "nomic-embed-text:latest"
_EMBEDDING_DIM = 768
_EMBEDDING_VERSION = "1"
_COLLECTION = "ura_documents"


def _get_qdrant() -> Any | None:
    """Retorna el singleton de QdrantClient o None si no está disponible."""
    try:
        from core.config import UraConfig
        from motor.core.qdrant_client import QdrantClient as MotorQdrant

        config = UraConfig()
        inst = MotorQdrant.instancia(config)
        if not hasattr(inst, "generar_embeddings_batch"):
            return None
        return inst
    except Exception as exc:
        log.debug("Qdrant no disponible: %s", exc)
        return None


def _chunk_version(doc: Document) -> str:
    """Versión estable del chunk basada en content_sha256.
    Cambia automáticamente cuando el contenido del documento cambia."""
    return doc.content_sha256[:12] if doc.content_sha256 else "0"


# ── Tracking en SQLite ────────────────────────────────────────────────────────


@contextmanager
def _track_conn(db_path: Path):
    """Context manager: una sola conexión SQLite para todo el batch sync."""
    conn = open_db(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _track_operation(
    conn: sqlite3.Connection,
    doc_id: str,
    operation: str,
    status: str,
    error: str = "",
    run_id: int = 0,
) -> None:
    """Inserta o actualiza un registro en op_vector_sync.

    Si attempts >= MAX_SYNC_ATTEMPTS y la operación sigue fallando,
    se marca como dead_letter automáticamente.
    Llama a conn.commit() internamente — el caller debe manejar rollback.
    """
    if status == "failed":
        conn.execute(
            "INSERT INTO op_vector_sync "
            "(doc_id, operation, run_id, status, last_error, attempts, created_at, updated_at) "
            "VALUES (?, ?, ?, 'failed', ?, 1, datetime('now'), datetime('now')) "
            "ON CONFLICT(doc_id, operation, run_id) DO UPDATE SET "
            "  status=CASE WHEN attempts+1 >= ? THEN 'dead_letter' ELSE 'failed' END, "
            "  last_error=excluded.last_error, attempts=attempts+1, "
            "  updated_at=datetime('now')",
            (doc_id, operation, run_id, error, MAX_SYNC_ATTEMPTS),
        )
    else:
        conn.execute(
            "INSERT INTO op_vector_sync "
            "(doc_id, operation, run_id, status, last_error, attempts, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, '', 0, datetime('now'), datetime('now')) "
            "ON CONFLICT(doc_id, operation, run_id) DO UPDATE SET "
            "  status=excluded.status, last_error='', attempts=0, "
            "  updated_at=datetime('now')",
            (doc_id, operation, run_id, status),
        )


def _sync_upsert(client: Any, doc: Document) -> bool:
    """Chunk → embed → upsert un documento en Qdrant. Retorna True si ok."""
    chunks = chunk_document(doc)
    if not chunks:
        return True

    cver = _chunk_version(doc)
    texts = [c.text for c in chunks]
    try:
        embeddings = client.generar_embeddings_batch(texts)
    except Exception as exc:
        log.warning("Error generando embeddings para %s: %s", doc.doc_id, exc)
        return False

    points = []
    for i, chunk in enumerate(chunks):
        if i >= len(embeddings):
            break
        vec = embeddings[i]
        if len(vec) != _EMBEDDING_DIM:
            log.warning("Dim inesperada para %s[%d]: %d", doc.doc_id, i, len(vec))
            continue
        point_id = f"{doc.doc_id}_{chunk.chunk_index}"
        points.append(
            {
                "id": point_id,
                "vector": vec,
                "payload": {
                    "doc_id": doc.doc_id,
                    "chunk_index": chunk.chunk_index,
                    "text": chunk.text,
                    "doc_type": doc.doc_type,
                    "path": doc.path,
                    "title": doc.frontmatter.title or "",
                    "chunk_version": cver,
                    "embed_model": _EMBEDDING_MODEL,
                    "embed_dim": _EMBEDDING_DIM,
                    "embed_version": _EMBEDDING_VERSION,
                    "embedding_created_at": __import__("datetime").datetime.now().isoformat(),
                },
            }
        )

    if not points:
        return True

    try:
        client.guardar_documentos_batch(_COLLECTION, points)
        return True
    except Exception as exc:
        log.warning("Error upsert %s: %s", doc.doc_id, exc)
        return False


def _sync_delete(client: Any, doc_id: str) -> bool:
    """Elimina todos los chunks de un documento de Qdrant."""
    try:
        return bool(
            client.eliminar_por_filtro(
                {"must": [{"key": "doc_id", "match": {"value": doc_id}}]},
                collection=_COLLECTION,
            )
        )
    except Exception as exc:
        log.warning("Error delete %s de Qdrant: %s", doc_id, exc)
        return False


# ── API pública ───────────────────────────────────────────────────────────────


def sync_documents(
    db_path: Path,
    docs: list[Document],
    deleted_ids: list[str],
    run_id: int = 0,
) -> int:
    """Sincroniza documentos con Qdrant: upsert + delete.

    Cada operación se registra en op_vector_sync para reintento.
    Fallos individuales no afectan al compile (graceful degradation).
    Retorna número de documentos sincronizados exitosamente.
    """
    client = _get_qdrant()
    if client is None:
        log.info("Qdrant no disponible — guardando tracking para reintento")
        with _track_conn(db_path) as conn:
            for doc in docs:
                _track_operation(conn, doc.doc_id, "upsert", "pending", run_id=run_id)
            for did in deleted_ids:
                _track_operation(conn, did, "delete", "pending", run_id=run_id)
        return 0

    synced = 0
    with _track_conn(db_path) as conn:
        for doc in docs:
            ok = _sync_upsert(client, doc)
            _track_operation(conn, doc.doc_id, "upsert", "done" if ok else "failed", run_id=run_id)
            if ok:
                synced += 1

        for did in deleted_ids:
            ok = _sync_delete(client, did)
            _track_operation(conn, did, "delete", "done" if ok else "failed", run_id=run_id)
            if ok:
                synced += 1

    return synced


def retry_failed(db_path: Path) -> int:
    """Reintenta operaciones fallidas de op_vector_sync.

    No reintenta upserts (requieren el Document completo).
    Solo procesa deletes pendientes. Marca dead_letter si excede MAX_SYNC_ATTEMPTS.
    Retorna número de operaciones recuperadas.
    """
    try:
        conn = open_db(db_path)
        rows = conn.execute(
            "SELECT doc_id, operation, run_id, attempts FROM op_vector_sync "
            "WHERE status IN ('pending', 'failed') AND attempts < ?",
            (MAX_SYNC_ATTEMPTS,),
        ).fetchall()
        conn.close()
    except Exception as exc:
        log.warning("Error leyendo op_vector_sync: %s", exc)
        return 0

    if not rows:
        return 0

    client = _get_qdrant()
    if client is None:
        return 0

    recovered = 0
    with _track_conn(db_path) as conn:
        for doc_id, operation, run_id, _ in rows:
            if operation == "upsert":
                continue
            ok = _sync_delete(client, doc_id) if operation == "delete" else False
            if ok:
                _track_operation(conn, doc_id, operation, "done", run_id=run_id)
                recovered += 1

    return recovered


def get_pending_delete_ids(db_path: Path) -> list[str]:
    """Retorna doc_ids con operación 'delete' pendiente/failed.

    Útil para que el Reader filtre documentos fantasma
    que aún existen en Qdrant pero ya no en SQLite.
    """
    try:
        conn = open_db(db_path)
        rows = conn.execute(
            "SELECT DISTINCT doc_id FROM op_vector_sync WHERE operation = 'delete' AND status IN ('pending', 'failed')",
        ).fetchall()
        conn.close()
        return [r[0] for r in rows]
    except Exception as exc:
        log.debug("Error leyendo pending_delete: %s", exc)
        return []


def search_semantic(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """Búsqueda semántica en Qdrant. Retorna hits con payload + score."""
    client = _get_qdrant()
    if client is None:
        return []
    try:
        results = client.buscar_documentos(_COLLECTION, query, top_k=top_k)
        return [
            {
                "doc_id": r.payload.get("doc_id", ""),
                "chunk_index": r.payload.get("chunk_index", 0),
                "text": r.payload.get("text", ""),
                "title": r.payload.get("title", ""),
                "score": r.score,
                "chunk_version": r.payload.get("chunk_version", ""),
            }
            for r in results
        ]
    except Exception as exc:
        log.warning("Error en búsqueda semántica: %s", exc)
        return []

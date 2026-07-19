"""Subscriptores del Event Bus — conectan eventos con servicios.

Cada función es un handler que se registra en el Event Bus.
Los handlers son best-effort: nunca lanzan excepciones.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from knowledge.engine.vector_base import Embedder, VectorStore

from knowledge.engine.eventbus import (
    ArchiveCompleted,
    CompileCompleted,
    EventBus,
    MetadataExtracted,
    SearchPerformed,
)

log = logging.getLogger("ura.knowledge.subscribers")


def subscribe_all(
    bus: EventBus,
    db_path: Path,
    source_dir: Path,
    vector_embedder: Embedder | None = None,
    vector_store: VectorStore | None = None,
) -> None:
    """Registra todos los subscriptores del sistema.

    Args:
        bus: Instancia del Event Bus.
        db_path: Ruta a la base de datos.
        source_dir: Ruta al directorio fuente.
        vector_embedder: Embedder para indexación vectorial (opcional).
        vector_store: VectorStore para indexación vectorial (opcional).

    """
    bus.subscribe(CompileCompleted, _make_compile_archive_handler(db_path, source_dir))
    bus.subscribe(CompileCompleted, _make_compile_audit_handler())
    bus.subscribe(CompileCompleted, _make_compile_metrics_handler())
    bus.subscribe(CompileCompleted, _make_lineage_subscriber(db_path))
    bus.subscribe(SearchPerformed, _make_search_audit_handler())
    bus.subscribe(ArchiveCompleted, _make_archive_metrics_handler())
    if vector_embedder is not None and vector_store is not None:
        bus.subscribe(
            MetadataExtracted,
            _make_vector_index_subscriber(db_path, vector_embedder, vector_store),
        )


def _make_compile_archive_handler(db_path: Path, source_dir: Path):
    """Handler: encola archive job post-compile."""

    def handler(event: CompileCompleted) -> None:
        try:
            from knowledge.engine.jobs import enqueue_archive_job, process_archive_jobs

            enqueue_archive_job(db_path, source_dir, event.correlation_id)
            process_archive_jobs(db_path, event.correlation_id)
        except Exception as exc:
            log.warning("Archive handler failed: %s", exc)

    return handler


def _make_compile_audit_handler():
    """Handler: registra auditoría post-compile."""

    def handler(event: CompileCompleted) -> None:
        try:
            from knowledge.engine.audit import get_audit

            get_audit().log_compile(
                result="success" if event.errors == 0 else "failure",
                correlation_id=event.correlation_id,
                docs_changed=event.documents_changed,
                errors=event.errors,
            )
        except Exception as exc:
            log.warning("Audit handler failed: %s", exc)

    return handler


def _make_compile_metrics_handler():
    """Handler: registra métricas post-compile."""

    def handler(event: CompileCompleted) -> None:
        try:
            from knowledge.engine.metrics import record_compile

            record_compile(source=event.reason)
        except Exception as exc:
            log.warning("Metrics handler failed: %s", exc)

    return handler


def _make_search_audit_handler():
    """Handler: registra auditoría de búsqueda."""

    def handler(event: SearchPerformed) -> None:
        try:
            from knowledge.engine.audit import get_audit

            get_audit().log_read(
                query=event.query,
                docs=event.docs_returned,
                correlation_id=event.correlation_id,
            )
        except Exception as exc:
            log.warning("Search audit handler failed: %s", exc)

    return handler


def _make_archive_metrics_handler():
    """Handler: registra métricas de archive."""

    def handler(event: ArchiveCompleted) -> None:
        try:
            from knowledge.engine.metrics import record_archive

            record_archive(kind=event.kind, status="completed")
        except Exception as exc:
            log.warning("Archive metrics handler failed: %s", exc)

    return handler


def _make_lineage_subscriber(db_path: Path):
    """Handler: registra eventos OpenLineage cuando se completa un compile."""

    def handler(event: CompileCompleted) -> None:
        try:
            from knowledge.engine.lineage_store import SQLiteLineageStore

            store = SQLiteLineageStore(db_path)
            ol_event = {
                "eventType": "COMPLETE",
                "eventTime": datetime.now(UTC).isoformat(),
                "run": {"runId": event.correlation_id},
                "job": {"namespace": "knowledge.engine", "name": "compile", "facets": {}},
                "inputs": [{"namespace": "source", "name": event.reason}],
                "outputs": [{"namespace": "knowledge.db", "name": f"compile:{event.correlation_id}"}],
                "facets": {
                    "documents": {
                        "changed": event.documents_changed,
                        "total": event.documents_total,
                        "errors": event.errors,
                    },
                },
            }
            store.store_lineage_event(ol_event)
            log.debug("Lineage event stored for compile %s", event.correlation_id[:8])
        except Exception as exc:
            log.warning("Lineage handler failed: %s", exc)

    return handler


def _make_vector_index_subscriber(
    db_path: Path,
    embedder: Embedder,
    vector_store: VectorStore,
):
    """Handler: indexa vectores cuando se extraen metadatos.

    Escucha MetadataExtracted, obtiene el asset de AssetStore,
    genera embedding y lo almacena en VectorStore.
    """

    def handler(event: MetadataExtracted) -> None:
        try:
            if not event.success:
                return
            from knowledge.engine.asset_store import SQLiteAssetStore

            store = SQLiteAssetStore(db_path)
            asset = store.get_asset(event.asset_id)
            if asset is None:
                return
            text = asset.metadata.get("text_preview", "")[:500]
            if not text:
                return
            max_chars = min(500, embedder.max_input_tokens * 4) if embedder.max_input_tokens else 500
            truncated = text[:max_chars]
            from knowledge.engine.vector_base import VectorItem

            vectors = embedder.embed([truncated])
            if vectors:
                item = VectorItem(
                    asset_id=event.asset_id,
                    vector=vectors[0],
                    text_preview=text,
                )
                vector_store.upsert([item])
        except Exception as exc:
            log.warning("Vector index handler failed: %s", exc)

    return handler


def _make_governance_subscriber(db_path: Path):
    """Handler: registra políticas por defecto para nuevos assets."""

    def handler(event: CompileCompleted) -> None:
        try:
            from knowledge.engine.governance_store import SQLiteGovernanceStore

            store = SQLiteGovernanceStore(db_path)
            if event.documents_total > 0:
                store.set_policy(
                    asset_id=f"compile:{event.correlation_id}",
                    policy={"action": "read", "roles": ["*"]},
                    actor="system",
                )
        except Exception as exc:
            log.warning("Governance handler failed: %s", exc)

    return handler

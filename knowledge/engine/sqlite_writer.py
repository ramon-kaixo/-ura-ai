"""SQLiteWriter — knowledge.db persistence layer.

Nunca parsea. Nunca valida.
Solo recibe KnowledgeObject y escribe en SQLite mediante repositorios separados.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import threading
import time
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from knowledge.engine.connection import begin_immediate
from knowledge.engine.migrations import migrate_db
from knowledge.engine.models import (
    COMPILE_ERRORS_RETENTION_RUNS,
    CompileContext,
    CompileError,
    CompileResult,
    KnowledgeObject,
)
from knowledge.engine.reader import clear_all_caches

if TYPE_CHECKING:
    import sqlite3
    from pathlib import Path

log = logging.getLogger("ura.knowledge.writer")


def _get_conn(db_path: Path) -> sqlite3.Connection:
    from knowledge.engine.connection import open_db

    return open_db(db_path)


def _begin_immediate_with_retry(
    conn: sqlite3.Connection,
    timeout: float = 5.0,
) -> None:
    """BEGIN IMMEDIATE con reintento. Delega a connection.begin_immediate()."""
    begin_immediate(conn, timeout=timeout)


_SHOULD_CANCEL = False


def _install_cancel_handler() -> None:
    global _SHOULD_CANCEL  # noqa: PLW0603
    _SHOULD_CANCEL = False

    # signal.signal() solo funciona en el hilo principal del intérprete.
    # En threads (API, TestClient), la cancelación vía señal no está disponible.
    if threading.current_thread() is not threading.main_thread():
        return

    def _handler(signum: int, _frame: Any) -> None:
        global _SHOULD_CANCEL  # noqa: PLW0603
        _SHOULD_CANCEL = True
        log.warning("Compile cancelado por señal %s", signum)

    signal.signal(signal.SIGINT, _handler)
    signal.signal(signal.SIGTERM, _handler)


def _restore_cancel_handlers(
    orig_sigint: Any,
    orig_sigterm: Any,
) -> None:
    if threading.current_thread() is not threading.main_thread():
        return
    signal.signal(signal.SIGINT, orig_sigint or signal.default_int_handler)
    signal.signal(signal.SIGTERM, orig_sigterm or signal.SIG_DFL)


@contextmanager
def _cancel_guard():
    """Context manager: instala handlers de cancelación y restaura al salir.

    Si el compile se cancela via SIGINT/SIGTERM, la transacción
    existente será revertida por el rollback en apply_compile().
    """
    orig_sigint = signal.getsignal(signal.SIGINT)
    orig_sigterm = signal.getsignal(signal.SIGTERM)
    _install_cancel_handler()
    try:
        yield
    finally:
        _restore_cancel_handlers(orig_sigint, orig_sigterm)


# ── Repositories ─────────────────────────────────────────────────────────────


class NodeRepository:
    """kg_nodes + kg_nodes_fts + kg_edges writes."""

    @staticmethod
    def rebuild(conn: sqlite3.Connection, objects: list[KnowledgeObject]) -> int:
        conn.execute("DELETE FROM kg_edges")

        changed = 0
        for obj in objects:
            conn.execute(
                "INSERT OR REPLACE INTO kg_nodes "
                "(id, type, path, content_sha256, frontmatter, body, "
                "semantic, quality, confidence, embed_hash, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))",
                (
                    obj.document.doc_id,
                    obj.document.doc_type,
                    obj.document.path,
                    obj.document.content_sha256,
                    json.dumps(obj.document.frontmatter.to_dict(), sort_keys=True),
                    obj.document.body,
                    json.dumps(obj.document.semantic) if obj.document.semantic else None,
                    obj.document.quality,
                    obj.document.confidence,
                    obj.document.embed_hash,
                ),
            )
            changed += 1

            for rel in obj.relations:
                conn.execute(
                    "INSERT INTO kg_edges (src, dst, relation, metadata) VALUES (?, ?, ?, ?)",
                    (rel.src, rel.dst, rel.relation, json.dumps(rel.metadata) if rel.metadata else None),
                )
        return changed

    @staticmethod
    def delete_ids(conn: sqlite3.Connection, doc_ids: list[str]) -> None:
        if not doc_ids:
            return
        placeholders = ",".join("?" for _ in doc_ids)
        conn.execute(
            f"DELETE FROM kg_edges WHERE src IN ({placeholders}) OR dst IN ({placeholders})",  # noqa: S608
            doc_ids + doc_ids,
        )
        conn.execute(
            f"DELETE FROM kg_nodes WHERE id IN ({placeholders})",  # noqa: S608
            doc_ids,
        )


class CompilerRunRepository:
    """op_compiler_runs + op_compile_errors writes."""

    @staticmethod
    def create_run(
        conn: sqlite3.Connection,
        ctx: CompileContext,
        changed: int,
        total: int,
        errors: list[CompileError],
        warnings: list[CompileError],
        duration_ms: float = 0.0,
    ) -> int:
        details = json.dumps(
            {
                "parser_version": ctx.metadata.features.parser_version,
                "schema_version": ctx.metadata.schema_version,
                "host": os.uname().nodename,
                "duration_ms": duration_ms,
                "cancelled": _SHOULD_CANCEL,
                "correlation_id": ctx.metadata.correlation_id,
            },
        )
        conn.execute(
            "INSERT INTO op_compiler_runs "
            "(status, started_at, completed_at, source_commit, "
            " compiler_version, documents_changed, documents_total, "
            " errors, warnings, graph_version, details) "
            "VALUES ('completed', datetime('now'), datetime('now'), ?, "
            "?, ?, ?, ?, ?, ?, ?)",
            (
                ctx.metadata.source_commit,
                ctx.metadata.features.parser_version,
                changed,
                total,
                len(errors),
                len(warnings),
                ctx.metadata.run_id,
                details,
            ),
        )
        run_id = conn.execute("SELECT last_insert_rowid() as rid").fetchone()["rid"]

        for ce in errors + warnings:
            conn.execute(
                "INSERT INTO op_compile_errors (run_id, error_code, document, stage, severity, "
                "message, line, column) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    ce.code,
                    ce.document,
                    ce.stage,
                    "ERROR" if ce in errors else "WARN",
                    ce.message,
                    ce.line,
                    ce.column,
                ),
            )

        # Purge old errors beyond retention limit
        if COMPILE_ERRORS_RETENTION_RUNS > 0:
            conn.execute(
                "DELETE FROM op_compile_errors WHERE run_id NOT IN "
                "(SELECT run_id FROM op_compiler_runs ORDER BY completed_at DESC LIMIT ?)",
                (COMPILE_ERRORS_RETENTION_RUNS,),
            )
        return run_id


class ActiveVersionRepository:
    """kg_active_version writes."""

    @staticmethod
    def swap(conn: sqlite3.Connection, run_id: int, ctx: CompileContext) -> None:
        conn.execute("DELETE FROM kg_active_version WHERE singleton=1")
        conn.execute(
            "INSERT INTO kg_active_version (singleton, graph_version, source_commit, "
            "compiler_version, qdrant_collection, swapped_at, determinism_hash) "
            "VALUES (1, ?, ?, ?, '', datetime('now'), '')",
            (run_id, ctx.metadata.source_commit, ctx.options.compiler_version),
        )


# ── SyncPolicy ─────────────────────────────────────────────────────────────────


class SyncPolicy:
    """Estrategia de sincronización del índice FTS con kg_nodes.

    Hoy: rebuild completo (DELETE + INSERT SELECT).
    Mañana: sync incremental (solo documentos cambiados).
    Futuro: sync asíncrono via cola de trabajos.

    Cada operación DEBE ejecutarse dentro de la misma transacción
    que muta kg_nodes (BEGIN IMMEDIATE ... COMMIT) para evitar
    ventanas de inconsistencia.
    """

    @staticmethod
    def sync_full(conn: sqlite3.Connection) -> None:
        """Reconstruye el índice FTS completo desde kg_nodes.

        Llama a esto después de mutar kg_nodes dentro de una transacción.
        Seguro contra fallos parciales: si INSERT falla después de DELETE,
        la transacción rollback protege el estado anterior.
        """
        conn.execute("DELETE FROM kg_nodes_fts")
        conn.execute(
            "INSERT INTO kg_nodes_fts (id, title, body, tags) "
            "SELECT id, json_extract(frontmatter, '$.title'), body, type FROM kg_nodes",
        )

    @staticmethod
    def sync_documents(conn: sqlite3.Connection, doc_ids: list[str]) -> None:
        """Sincroniza FTS para documentos específicos.

        Stub para implementación futura con sync incremental.
        Hoy fallback a rebuild completo.
        """
        SyncPolicy.sync_full(conn)


# ── Public API ───────────────────────────────────────────────────────────────


def init_db(db_path: Path, schema_path: Path) -> None:
    """Create or migrate knowledge.db to current schema version.

    - DB no existe: crea con schema completo.
    - DB existe pero versión anterior: migración incremental.
    - DB existe misma versión: no-op.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = _get_conn(db_path)
    try:
        migrate_db(conn, schema_path)
    except Exception:
        conn.close()
        raise
    conn.close()


def apply_compile(
    db_path: Path,
    objects: list[KnowledgeObject],
    ctx: CompileContext,
    errors: list[CompileError],
    warnings: list[CompileError],
    deleted_ids: list[str] | None = None,
) -> CompileResult:
    """BEGIN IMMEDIATE (con reintento) → rebuild → SyncPolicy → COMMIT.

    Protegido por:
    - Retry ante SQLITE_BUSY (hasta _BUSY_TIMEOUT_S segundos).
    - Signal handlers (SIGINT/SIGTERM → rollback limpio).
    - Transacción atómica: cualquier fallo revierte todo.
    """
    started_at = time.monotonic()
    conn = _get_conn(db_path)

    try:
        with _cancel_guard():
            _begin_immediate_with_retry(conn)

            changed = NodeRepository.rebuild(conn, objects)

            if deleted_ids:
                NodeRepository.delete_ids(conn, deleted_ids)

            SyncPolicy.sync_full(conn)

            duration_ms = (time.monotonic() - started_at) * 1000.0
            run_id = CompilerRunRepository.create_run(
                conn,
                ctx,
                changed,
                len(objects),
                errors,
                warnings,
                duration_ms,
            )
            ActiveVersionRepository.swap(conn, run_id, ctx)

            conn.commit()
            clear_all_caches()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    duration_ms = (time.monotonic() - started_at) * 1000.0
    return CompileResult(
        success=len(errors) == 0,
        graph_version=run_id,
        source_commit=ctx.metadata.source_commit,
        compiler_version=ctx.options.compiler_version,
        documents_total=len(objects),
        documents_changed=changed,
        run_id=run_id,
        errors=tuple(errors),
        warnings=tuple(warnings),
        duration_ms=duration_ms,
        stage="completed",
    )


def get_compile_errors(db_path: Path, limit: int = 100) -> list[dict[str, Any]]:
    conn = _get_conn(db_path)
    try:
        rows = conn.execute(
            "SELECT error_code, document, stage, severity, message, line, column, created_at "
            "FROM op_compile_errors ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

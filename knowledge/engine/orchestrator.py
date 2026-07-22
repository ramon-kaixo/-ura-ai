"""Orchestrator — único punto de entrada al compile.

Toda solicitud de compilación (watcher, git hook, scheduler, agente, API)
pasa por `request_compile()`. Nadie llama a `apply_compile()` directamente
excepto el worker (`compile_worker`).

El correlation_id nace aquí y se propaga a compilador, archivador, logs.

PRINCIPIO: El orchestrator NO contiene lógica de negocio.
            Solo coordina. La lógica vive en:
              - compiler.py
              - jobs.py
              - lock.py
              - determinism.py
              - metrics.py
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from pathlib import Path

from knowledge.engine.compiler import compile_source
from knowledge.engine.eventbus import CompileCompleted, get_bus
from knowledge.engine.jobs import compile_worker as jobs_compile_worker
from knowledge.engine.jobs import enqueue_archive_job, process_archive_jobs
from knowledge.engine.lock import LockAcquisitionError, compile_lock
from knowledge.engine.logging_config import set_correlation_id
from knowledge.engine.metrics import record_compile
from knowledge.engine.reader import clear_all_caches

log = logging.getLogger("ura.knowledge.orchestrator")

_DEDUP_WINDOW_S = 30


def _default_dedup_key(payload: dict | None) -> str:
    """Clave de deduplicación por defecto: sha256 del payload."""
    raw = json.dumps(payload or {}, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def request_compile(
    reason: str,
    *,
    payload: dict | None = None,
    dedup_key: str | None = None,
    db_path: Path | None = None,
    source_dir: Path | None = None,
) -> int:
    """Solicita una compilación. Retorna número de trabajos procesados (0 o 1).

    Por ahora ejecuta síncronamente (sin cola de trabajos) con protección
    por flock. En Fase E se migrará a op_jobs asíncrono.

    db_path y source_dir permiten sobreescribir rutas (usado en tests).
    """
    key = dedup_key or _default_dedup_key(payload)
    return _execute_compile(reason, key, db_path=db_path, source_dir=source_dir)


def _execute_compile(
    reason: str,
    dedup_key: str,
    db_path: Path | None = None,
    source_dir: Path | None = None,
) -> int:
    """Ejecuta el compile con exclusión mutua vía flock.

    correlation_id nace aquí (único punto de origen).
    """
    if source_dir is None:
        source_dir = Path(__file__).resolve().parent.parent.parent / "source"
    if db_path is None:
        db_path = Path.home() / "URA" / "ura_ia_1972" / "knowledge" / "knowledge.db"

    try:
        with compile_lock():
            correlation_id = uuid.uuid4().hex
            set_correlation_id(correlation_id)
            log.info(
                "Compile iniciado correlation_id=%s reason=%s",
                correlation_id[:12],
                reason,
            )
            try:
                result = compile_source(
                    source_dir=source_dir,
                    db_path=db_path,
                    compiler_version="0.1.0",
                    correlation_id=correlation_id,
                )

                if result.success:
                    record_compile(source=reason)
                    enqueue_archive_job(db_path, source_dir, correlation_id)
                    process_archive_jobs(db_path, correlation_id)
                    get_bus().publish(
                        CompileCompleted(
                            reason=reason,
                            documents_changed=result.documents_changed,
                            documents_total=result.documents_total,
                            errors=len(result.errors),
                            correlation_id=correlation_id,
                        ),
                    )

                log.info(
                    "Compile completado cid=%s success=%s changed=%d total=%d errors=%d",
                    correlation_id[:8],
                    result.success,
                    result.documents_changed,
                    result.documents_total,
                    len(result.errors),
                )
                return 1
            except Exception:
                log.exception(
                    "Compile falló cid=%s reason=%s",
                    correlation_id[:8],
                    reason,
                )
                return 0
            finally:
                clear_all_caches()
    except LockAcquisitionError:
        log.info("Compile ya en ejecución — saltando (reason=%s)", reason)
        return 0


def compile_result_to_claims(db_path: Path) -> list:
    """Convierte documentos compilados en KnowledgeClaims para fusión.

    Lee kg_nodes de la BD y genera un KnowledgeClaim por documento
    con subject=tipo, predicate='documents', object=título.
    """
    from knowledge.engine.connection import open_db

    conn = open_db(db_path)
    rows = conn.execute("SELECT id, type, path, frontmatter, body FROM kg_nodes").fetchall()
    conn.close()

    from motor.core.fusion.models import KnowledgeClaim, make_claim_id

    claims: list = []
    for r in rows:
        fm = json.loads(r["frontmatter"]) if r["frontmatter"] else {}
        title = fm.get("title", r["id"])
        body = r["body"] or ""
        text = f"{title}: {body[:200].strip()}" if body else title
        claim = KnowledgeClaim(
            id=make_claim_id(r["id"], title),
            text=text,
            confidence=0.8,
            subject=r["type"],
            predicate="documents",
            object=title,
            text_id=r["id"],
        )
        claims.append(claim)
    return claims


def compile_worker(db_path: Path | None = None, source_dir: Path | None = None) -> int:
    """Worker independiente para systemd timer.

    Lee trabajos de compilación pendientes de op_jobs y los ejecuta.
    También procesa archive jobs pendientes.

    NO pasa por request_compile() — llama a jobs.compile_worker()
    que invoca compile_source() directamente para evitar re-encolados.

    Llamado por 'ke job-process' cada 5 minutos.
    Retorna número de trabajos procesados.
    """
    if source_dir is None:
        source_dir = Path(__file__).resolve().parent.parent.parent / "source"
    if db_path is None:
        db_path = Path.home() / "URA" / "ura_ia_1972" / "knowledge" / "knowledge.db"

    n = jobs_compile_worker(db_path, source_dir)
    process_archive_jobs(db_path, "worker")
    return n

"""Job queue — op_jobs management for archive and compile tasks.

Responsabilidades:
  - Encolar archive_source jobs (fire-and-forget)
  - Procesar archive_source jobs (con stale recovery)
  - compile_worker para consumo por systemd timer

Arquitectura:
  El consumidor de op_jobs es un systemd timer que ejecuta
  `ke job-process` periódicamente (cada 5 minutos).
  No hay daemon ni thread interno — simplicidad operativa.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

from knowledge.engine.connection import begin_immediate, open_db

log = logging.getLogger("ura.knowledge.jobs")

_JOB_STALE_TIMEOUT_MINUTES = 5


def enqueue_archive_job(
    db_path: Path,
    source_dir: Path,
    correlation_id: str = "",
) -> None:
    """Encola un trabajo archive_source en op_jobs (fire-and-forget).

    Si ya existe un trabajo pending/running para la misma source_dir,
    el INSERT es ignorado (dedup_key).
    """
    dedup_key = hashlib.sha256(str(source_dir).encode()).hexdigest()[:16]
    payload = json.dumps(
        {
            "source_dir": str(source_dir),
            "db_path": str(db_path),
            "correlation_id": correlation_id,
        }
    )
    try:
        conn = open_db(db_path)
        begin_immediate(conn)
        conn.execute(
            "INSERT OR IGNORE INTO op_jobs "
            "(job_type, status, payload, dedup_key, created_at) "
            "VALUES ('archive_source', 'pending', ?, ?, datetime('now'))",
            (payload, dedup_key),
        )
        conn.commit()
        conn.close()
        log.info(
            "Archive job enqueued: dedup=%s cid=%s",
            dedup_key,
            correlation_id[:8] if correlation_id else "-",
        )
    except Exception as exc:
        log.warning("No se pudo encolar archive job: %s", exc)


def process_archive_jobs(
    db_path: Path,
    correlation_id: str = "",
) -> None:
    """Procesa trabajos archive_source pendientes (fire-and-forget).

    Incluye recuperación de jobs 'running' atascados (stale recovery).
    Si un archive falla, el compile NO se revierte.
    """
    from knowledge.engine.archiver import archive_source
    from knowledge.engine.metrics import record_archive

    try:
        conn = open_db(db_path)
        begin_immediate(conn)

        _recover_stale_jobs(conn)

        jobs = conn.execute(
            "SELECT id, payload FROM op_jobs WHERE job_type = 'archive_source' AND status = 'pending'"
        ).fetchall()

        for job in jobs:
            job_id = job["id"]
            payload = json.loads(job["payload"])

            conn.execute(
                "UPDATE op_jobs SET status = 'running', started_at = datetime('now') WHERE id = ?",
                (job_id,),
            )
            conn.commit()

            try:
                src = Path(payload["source_dir"])
                if not src.is_absolute():
                    raise ValueError(f"source_dir del payload no es absoluto: {src}")
                src = src.resolve()
                p = Path(payload.get("db_path", str(db_path)))
                if p != db_path:
                    if not p.is_absolute():
                        raise ValueError(f"db_path del payload no es absoluto: {p}")
                    p = p.resolve()
                archive_source(source_dir=src, db_path=p)
                begin_immediate(conn)
                conn.execute(
                    "UPDATE op_jobs SET status = 'completed', completed_at = datetime('now') WHERE id = ?",
                    (job_id,),
                )
                record_archive(kind="source", status="completed")
                log.info(
                    "Archive job %d completed (cid=%s)",
                    job_id,
                    correlation_id[:8] if correlation_id else "-",
                )
            except Exception as exc:
                log.warning(
                    "Archive job %d failed: %s (cid=%s)",
                    job_id,
                    exc,
                    correlation_id[:8] if correlation_id else "-",
                )
                record_archive(kind="source", status="failed")
                begin_immediate(conn)
                conn.execute(
                    "UPDATE op_jobs SET status = 'failed', error = ?, completed_at = datetime('now') WHERE id = ?",
                    (str(exc), job_id),
                )
            conn.commit()

        conn.close()
    except Exception as exc:
        log.warning("Error procesando archive jobs: %s", exc)


def _recover_stale_jobs(conn) -> None:
    """Recupera jobs 'running' atascados (crash sin finalizar).

    Los resetea a 'pending' para que sean reprocesados.
    """
    conn.execute(
        "UPDATE op_jobs SET status = 'pending', error = 'stale (recovered)', "
        "started_at = NULL "
        "WHERE job_type = 'archive_source' AND status = 'running' "
        "AND started_at < datetime('now', ?)",
        (f"-{_JOB_STALE_TIMEOUT_MINUTES} minutes",),
    )
    n_stale = conn.execute("SELECT changes()").fetchone()[0]
    if n_stale:
        log.info("Recovered %d stale archive jobs", n_stale)
        _inc_job_retry("archive_source", "stale", n_stale)


def _inc_job_retry(job_type: str, reason: str, count: int = 1) -> None:
    try:
        from knowledge.engine.metrics import job_retry_total

        for _ in range(count):
            job_retry_total.labels(job_type=job_type, reason=reason).inc()
    except Exception:
        pass


def compile_worker(db_path: Path, source_dir: Path) -> int:
    """Worker independiente para systemd timer.

    Lee trabajos de compilación pendientes de op_jobs y los ejecuta.
    NO pasa por request_compile() para evitar el re-encolado de archive jobs.

    Llamado por 'ke job-process' (systemd timer cada 5 min).
    """
    from knowledge.engine.compiler import compile_source
    from knowledge.engine.lock import LockAcquisitionError, compile_lock

    processed = 0
    try:
        conn = open_db(db_path)
        jobs = conn.execute(
            "SELECT id, payload FROM op_jobs "
            "WHERE job_type = 'compile' AND status = 'pending' "
            "ORDER BY priority DESC, created_at ASC"
        ).fetchall()
        conn.close()
    except Exception as exc:
        log.warning("Error leyendo compile jobs: %s", exc)
        return 0

    for job in jobs:
        try:
            with compile_lock():
                result = compile_source(
                    source_dir=source_dir,
                    db_path=db_path,
                    compiler_version="0.1.0",
                )
            if result.success:
                _mark_job_done(db_path, job["id"])
                processed += 1
            else:
                _mark_job_failed(db_path, job["id"], "; ".join(str(e) for e in result.errors))
        except LockAcquisitionError:
            log.info("Compile lock ocupado — salteando job %d", job["id"])
            break
        except Exception as exc:
            _mark_job_failed(db_path, job["id"], str(exc))
            log.warning("Compile job %d failed: %s", job["id"], exc)

    return processed


def _mark_job_done(db_path: Path, job_id: int) -> None:
    try:
        conn = open_db(db_path)
        begin_immediate(conn)
        conn.execute(
            "UPDATE op_jobs SET status = 'completed', completed_at = datetime('now') WHERE id = ?",
            (job_id,),
        )
        conn.commit()
        conn.close()
    except Exception as exc:
        log.debug("Error marking job %d done: %s", job_id, exc)


def _mark_job_failed(db_path: Path, job_id: int, error: str) -> None:
    try:
        conn = open_db(db_path)
        begin_immediate(conn)
        conn.execute(
            "UPDATE op_jobs SET status = 'failed', error = ?, completed_at = datetime('now') WHERE id = ?",
            (error, job_id),
        )
        conn.commit()
        conn.close()
    except Exception as exc:
        log.debug("Error marking job %d failed: %s", job_id, exc)

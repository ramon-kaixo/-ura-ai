"""MetadataExtractionService — orquesta la extracción de metadatos.

Flujo:
  Source (archivo .md, .pdf, etc.)
    → ExtractorRegistry.get_for_mime()
    → Extractor.extract()
    → AssetStore.save_asset()
    → KnowledgeAsset

Sin modificar compiler.py. Este servicio se ejecuta desde el pipeline
o desde un EventBus subscriber.
"""

from __future__ import annotations

import hashlib
import json
import logging
import multiprocessing
import sqlite3
import threading
from pathlib import Path
from typing import Any

from knowledge.engine.asset_store import AssetStore, SQLiteAssetStore
from knowledge.engine.connection import begin_immediate, open_db
from knowledge.engine.eventbus import MetadataExtracted, get_bus
from knowledge.engine.extractors.base import ExtractorRegistry, get_registry
from knowledge.engine.ontology.internal import AssetSource, AssetType

log = logging.getLogger("ura.knowledge.extraction_service")

_MAX_BACKGROUND_WORKERS = 1  # fijo para MVP. Multi-worker en Fase 8+
_MAX_EXTRACTION_TIME = 300  # segundos (5 min)
_MAX_RUNNING_INTERVAL = "-900"  # 15 min en formato SQL
_POLL_INTERVAL = 0.5  # segundos entre polls

_EXTRACTION_SEMAPHORES: dict[str, threading.BoundedSemaphore] = {}
_MAX_CONCURRENT_PER_EXTRACTOR = 1


def _get_semaphore(extractor_id: str) -> threading.BoundedSemaphore:
    if extractor_id not in _EXTRACTION_SEMAPHORES:
        _EXTRACTION_SEMAPHORES[extractor_id] = \
            threading.BoundedSemaphore(_MAX_CONCURRENT_PER_EXTRACTOR)
    return _EXTRACTION_SEMAPHORES[extractor_id]


class MetadataExtractionService:
    """Orquesta la extracción de metadatos para un source.

    Uso:
        service = MetadataExtractionService(db_path, registry)
        result = service.extract(AssetSource("filesystem", "/path/to/doc.md"))
    """

    def __init__(self, db_path: Path, registry: ExtractorRegistry | None = None,
                 store: AssetStore | None = None):
        self._db_path = db_path
        self._registry = registry or get_registry()
        self._store: AssetStore = store or SQLiteAssetStore(db_path)
        self._worker_thread: threading.Thread | None = None
        self._worker_stop: threading.Event = threading.Event()
        self._running_jobs: dict[int, multiprocessing.Process] = {}
        self._jobs_lock: threading.Lock = threading.Lock()

    def queue_extract(self, source: AssetSource) -> str:
        """Encola extracción. Retorna job_id (str) para seguimiento.

        Si ya existe un job con el mismo dedup_key (misma location),
        retorna el job_id existente sin crear duplicado.
        """
        dedup = hashlib.sha256(source.location.encode()).hexdigest()
        conn = open_db(self._db_path)
        try:
            try:
                cur = conn.execute(
                    "INSERT INTO op_jobs "
                    "(job_type, priority, status, payload, dedup_key, created_at) "
                    "VALUES ('extraction', 0, 'pending', ?, ?, datetime('now'))",
                    (json.dumps({"kind": source.kind, "location": source.location}), dedup),
                )
                conn.commit()
                return str(cur.lastrowid)
            except sqlite3.IntegrityError:
                conn.rollback()
                row = conn.execute(
                    "SELECT id FROM op_jobs WHERE dedup_key = ?", (dedup,)
                ).fetchone()
                if row is not None:
                    return str(row["id"])
                # Caso raro: carrera donde se insertó entre el error y la consulta
                # Reintentar INSERT
                cur = conn.execute(
                    "INSERT INTO op_jobs "
                    "(job_type, priority, status, payload, dedup_key, created_at) "
                    "VALUES ('extraction', 0, 'pending', ?, ?, datetime('now'))",
                    (json.dumps({"kind": source.kind, "location": source.location}), dedup),
                )
                conn.commit()
                return str(cur.lastrowid)
        finally:
            conn.close()

    def get_queue_status(self, job_id: str) -> dict[str, Any]:
        """Estado del job: status, error, result_data, started_at, completed_at."""
        conn = open_db(self._db_path)
        try:
            row = conn.execute(
                "SELECT status, error, result_data, started_at, completed_at "
                "FROM op_jobs WHERE id = ?", (int(job_id),)
            ).fetchone()
            if not row:
                return {"status": "not_found"}
            return dict(row)
        finally:
            conn.close()

    def start_worker(self):
        """Inicia el worker loop en un hilo background."""
        if self._worker_thread and self._worker_thread.is_alive():
            return
        self._worker_stop.clear()
        self._worker_thread = threading.Thread(
            target=_worker_loop,
            args=(self._db_path, self._registry, self._store, self._worker_stop,
                  self._running_jobs, self._jobs_lock, _MAX_BACKGROUND_WORKERS),
            daemon=True,
        )
        self._worker_thread.start()

    def stop_worker(self, timeout: float = 30.0):
        """Detiene el worker loop y termina procesos en ejecución."""
        self._worker_stop.set()
        with self._jobs_lock:
            for _job_id, proc in list(self._running_jobs.items()):
                if proc.is_alive():
                    proc.terminate()
                    proc.join(timeout=5)
                    if proc.is_alive():
                        proc.kill()
                        proc.join(timeout=0.1)
                proc.close()
        if self._worker_thread:
            self._worker_thread.join(timeout=timeout)

    def extract(self, source: AssetSource) -> dict[str, Any]:
        """Extrae metadatos de un source y los almacena.

        Args:
            source: AssetSource con location y kind.

        Returns:
            Dict con resultado de la extracción.
        """
        # Detectar MIME type por extensión
        mime = self._guess_mime(source.location)
        extractors = self._registry.get_for_mime(mime)

        if not extractors:
            return {"success": False, "error": f"No extractor for {mime}", "asset": None}

        results = []
        for extractor in extractors:
            result = extractor.extract(source)
            if result.errors:
                for err in result.errors:
                    log.warning("Extractor %s error for %s: %s", extractor.id, source.location, err)
                continue
            if result.asset:
                saved = self._store.save_asset(result.asset)
                results.append({
                    "extractor": extractor.id,
                    "version": extractor.version,
                    "asset_id": result.asset.asset_id,
                    "saved": saved,
                    "duration_ms": result.duration_ms,
                })
                log.info("Extracted %s with %s (v%s) in %.0fms",
                         source.location, extractor.id, extractor.version, result.duration_ms)
                if saved:
                    try:
                        get_bus().publish(MetadataExtracted(
                            asset_id=result.asset.asset_id,
                            asset_type=result.asset.asset_type,
                            extractor=extractor.id,
                            success=True,
                            duration_ms=result.duration_ms,
                        ))
                    except Exception as exc:
                        log.warning("Failed to publish MetadataExtracted: %s", exc)

        return {
            "success": len(results) > 0,
            "results": results,
            "asset": results[0].get("asset_id") if results else None,
        }

    def extract_path(self, path: Path) -> dict[str, Any]:
        """Extrae metadatos de un archivo del sistema de archivos."""
        source = AssetSource(kind="filesystem", location=str(path.resolve()))
        return self.extract(source)

    @staticmethod
    def _guess_mime(location: str) -> str:
        return _guess_mime(location)


# ── Worker loop (module-level, pickleable) ─────────────────────────────────


def _guess_mime(location: str) -> str:
    """Estima el MIME type por extensión de archivo."""
    ext = Path(location).suffix.lower()
    mime_map = {
        ".md": "text/markdown",
        ".markdown": "text/markdown",
        ".mdown": "text/markdown",
        ".txt": "text/plain",
        ".pdf": "application/pdf",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".avi": "video/avi",
        ".mp3": "audio/mp3",
        ".wav": "audio/wav",
        ".flac": "audio/flac",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".html": "text/html",
        ".htm": "text/html",
    }
    return mime_map.get(ext, "application/octet-stream")


def _worker_loop(db_path: Path, registry: ExtractorRegistry, store: AssetStore,  # noqa: C901, PLR0912, PLR0915
                 stop: threading.Event, running_jobs: dict, jobs_lock: threading.Lock,
                 max_workers: int = 1):
    """Loop principal del worker. Se ejecuta en un hilo DAEMON del proceso principal."""
    while not stop.is_set():
        conn = None
        try:
            conn = open_db(db_path)
            begin_immediate(conn, timeout=1.0)

            try:
                row = conn.execute("""
                    UPDATE op_jobs
                    SET status = 'running', started_at = datetime('now')
                    WHERE id IN (
                        SELECT id FROM op_jobs
                        WHERE job_type = 'extraction'
                          AND (status = 'pending'
                               OR (status = 'running' AND started_at IS NOT NULL
                                   AND started_at < datetime('now', ?)))
                        ORDER BY priority DESC, created_at ASC
                        LIMIT 1
                    )
                    RETURNING id, payload
                """, (_MAX_RUNNING_INTERVAL,)).fetchone()
            except sqlite3.OperationalError:
                conn.rollback()
                conn.close()
                conn = open_db(db_path)
                begin_immediate(conn, timeout=1.0)
                c = conn.execute("""
                    SELECT id, payload FROM op_jobs
                    WHERE job_type = 'extraction'
                      AND (status = 'pending'
                           OR (status = 'running' AND started_at IS NOT NULL
                               AND started_at < datetime('now', ?)))
                    ORDER BY priority DESC, created_at ASC
                    LIMIT 1
                """, (_MAX_RUNNING_INTERVAL,))
                sel = c.fetchone()
                if not sel:
                    conn.rollback()
                    conn.close()
                    conn = None
                    stop.wait(_POLL_INTERVAL)
                    continue
                conn.execute(
                    "UPDATE op_jobs SET status = 'running', started_at = datetime('now') WHERE id = ?",
                    (sel["id"],),
                )
                row = sel

            if not row:
                conn.rollback()
                conn.close()
                conn = None
                stop.wait(_POLL_INTERVAL)
                continue

            job_id = row["id"]
            payload = json.loads(row["payload"] or "{}")
            source = AssetSource(payload.get("kind", "unknown"), payload.get("location", ""))

            conn.commit()
            conn.close()
            conn = None

            mime = _guess_mime(source.location)
            extractors = registry.get_for_mime(mime)
            if not extractors:
                _mark_job_failed(db_path, job_id, f"No extractor for {mime}")
                continue

            extractor_id = extractors[0].id
            sem = _get_semaphore(extractor_id)

            if not sem.acquire(blocking=True, timeout=30):
                _mark_job_failed(db_path, job_id, f"Semaphore timeout for {extractor_id}")
                continue

            try:
                proc = multiprocessing.Process(
                    target=_extract_in_worker,
                    args=(db_path, job_id, source.location, source.kind, extractor_id),
                )
                with jobs_lock:
                    running_jobs[job_id] = proc
                    proc.start()
                proc.join(timeout=_MAX_EXTRACTION_TIME)

                if proc.is_alive():
                    proc.terminate()
                    proc.join(timeout=5)
                    if proc.is_alive():
                        proc.kill()
                    _mark_job_failed(db_path, job_id, "timeout after 300s")
                    with jobs_lock:
                        running_jobs.pop(job_id, None)
                    continue

                result = _read_job_result(db_path, job_id)
                if not result or result.get("status") == "failed":
                    with jobs_lock:
                        running_jobs.pop(job_id, None)
                    continue

                try:
                    get_bus().publish(MetadataExtracted(
                        asset_id=result["asset_id"],
                        asset_type=AssetType(result["asset_type"]),
                        extractor=extractor_id,
                        success=True,
                        duration_ms=result["duration_ms"],
                    ))
                except Exception as exc:
                    log.warning("Failed to publish MetadataExtracted for job %s: %s", job_id, exc)

                with jobs_lock:
                    running_jobs.pop(job_id, None)
            finally:
                sem.release()
                proc.join(timeout=0.1)
                proc.close()

        except Exception as exc:
            log.exception("Worker loop error: %s", exc)
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass


def _extract_in_worker(db_path: Path, job_id: int, location: str, kind: str, extractor_id: str):
    """Se ejecuta en PROCESO HIJO (fork).

    REGLAS:
      - NO importar EventBus (no hay suscriptores aquí)
      - NO tocar HTTP clients del padre (fork unsafe)
      - NO usar singletons del padre
      - Abrir conexión SQLite FRESCA
      - Cerrar todo antes de salir
    """
    logging.basicConfig(level=logging.WARNING, force=True)

    conn = None
    try:
        from knowledge.engine.asset_store import SQLiteAssetStore
        from knowledge.engine.connection import open_db
        from knowledge.engine.extractors.base import get_registry
        from knowledge.engine.ontology.internal import AssetSource

        conn = open_db(db_path)
        store = SQLiteAssetStore(db_path)

        registry = get_registry()
        extractor = registry.get(extractor_id)
        if extractor is None:
            _write_job_fail(conn, job_id, f"Extractor {extractor_id} not found")
            return

        source = AssetSource(kind, location)
        result = extractor.extract(source)

        if result.asset and not result.errors:
            saved = store.save_asset(result.asset)
            if saved:
                _write_job_done(conn, job_id, result.asset.asset_id,
                                result.asset.asset_type.value, result.duration_ms)
            else:
                _write_job_fail(conn, job_id, "AssetStore.save_asset() returned False")
        else:
            error_msg = result.errors[0] if result.errors else "unknown error"
            _write_job_fail(conn, job_id, error_msg)

    except Exception as exc:
        if conn is not None:
            try:
                _write_job_fail(conn, job_id, str(exc))
            except Exception:
                pass
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _write_job_done(conn, job_id, asset_id, asset_type, duration_ms):
    begin_immediate(conn)
    conn.execute(
        "UPDATE op_jobs SET status = 'done', completed_at = datetime('now'), "
        "result_data = ? WHERE id = ?",
        (json.dumps({
            "asset_id": asset_id,
            "asset_type": asset_type,
            "duration_ms": duration_ms,
        }), job_id),
    )
    conn.commit()


def _write_job_fail(conn, job_id, error):
    begin_immediate(conn)
    conn.execute(
        "UPDATE op_jobs SET status = 'failed', completed_at = datetime('now'), error = ? WHERE id = ?",
        (error, job_id),
    )
    conn.commit()


def _mark_job_failed(db_path, job_id, error):
    conn = open_db(db_path)
    try:
        begin_immediate(conn)
        conn.execute(
            "UPDATE op_jobs SET status = 'failed', completed_at = datetime('now'), error = ? WHERE id = ?",
            (error, job_id),
        )
        conn.commit()
    finally:
        conn.close()


def _read_job_result(db_path, job_id):
    conn = open_db(db_path)
    try:
        row = conn.execute(
            "SELECT status, result_data, error FROM op_jobs WHERE id = ?", (job_id,)
        ).fetchone()
        if not row:
            return None
        result = {"status": row["status"]}
        if row["result_data"]:
            result.update(json.loads(row["result_data"]))
        if row["error"]:
            result["error"] = row["error"]
        return result
    finally:
        conn.close()

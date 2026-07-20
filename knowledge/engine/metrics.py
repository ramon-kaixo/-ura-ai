"""Metrics — observabilidad pasiva del Knowledge Engine.

Principios:
- La observabilidad nunca modifica el flujo del sistema.
- Métricas del compilador se derivan de SQLite (persistentes entre procesos).
- Métricas del API/live están en memoria Prometheus (viven en el servidor).
- Un solo punto de exportación: export_metrics().

Uso esperado:

    from knowledge.engine.metrics import record_compile, export_metrics

    record_compile(source="scheduler")
    prometheus_data = export_metrics(db_path=Path("knowledge.db"))
    # servir prometheus_data en /metrics con Content-Type: text/plain
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from prometheus_client import REGISTRY, Counter, Gauge, Histogram, generate_latest

from knowledge.engine.connection import open_db

if TYPE_CHECKING:
    from pathlib import Path

log = logging.getLogger("ura.knowledge.metrics")

# ── In-memory Prometheus metrics (viven en el proceso API) ──────────────

search_requests = Counter(
    "ke_search_requests_total",
    "Total search requests processed",
    ["mode"],
)

search_duration = Histogram(
    "ke_search_duration_seconds",
    "Search request duration in seconds",
    ["mode"],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0),
)

qdrant_sync_ops = Counter(
    "ke_qdrant_sync_ops_total",
    "Qdrant sync operations by operation and status",
    ["operation", "status"],
)

compile_requests = Counter(
    "ke_compile_requests_total",
    "Compile requests triggered by source",
    ["source"],
)

archive_ops = Counter(
    "ke_archive_ops_total",
    "Archive operations by kind and status",
    ["kind", "status"],
)

errors_total = Counter(
    "ke_errors_total",
    "Knowledge Engine errors by error code",
    ["code"],
)

audit_write_failures = Counter(
    "ke_audit_write_failures_total",
    "Audit write failures (disk full, permissions, etc.)",
)

compile_lock_wait_seconds = Histogram(
    "ke_compile_lock_wait_seconds",
    "Time spent waiting for compile lock",
    buckets=(0.001, 0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0),
)

sqlite_busy_retries_total = Counter(
    "ke_sqlite_busy_retries_total",
    "SQLite busy retries during BEGIN IMMEDIATE",
)

job_retry_total = Counter(
    "ke_job_retry_total",
    "Job retry count by job type and reason",
    ["job_type", "reason"],
)

archive_duration_seconds = Histogram(
    "ke_archive_duration_seconds",
    "Archive creation duration in seconds",
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0),
)

audit_ingest_duration_seconds = Histogram(
    "ke_audit_ingest_duration_seconds",
    "Audit NDJSON → SQLite ingest duration in seconds",
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0),
)

# ── SQLite-derived gauges (se actualizan en cada export_metrics) ────────

db_nodes_total = Gauge(
    "ke_db_nodes_total",
    "Total nodes in kg_nodes",
)

db_edges_total = Gauge(
    "ke_db_edges_total",
    "Total edges in kg_edges",
)

db_compile_runs = Gauge(
    "ke_db_compile_runs_total",
    "Total compiler runs recorded",
)

db_compile_errors = Gauge(
    "ke_db_compile_errors_total",
    "Total compile errors (severity=ERROR)",
)

db_pending_sync = Gauge(
    "ke_db_pending_sync",
    "Qdrant sync operations pending or failed",
)

db_schema_version = Gauge(
    "ke_db_schema_version",
    "Current schema version (PRAGMA user_version)",
)

compile_queue_length = Gauge(
    "ke_compile_queue_length",
    "Compile jobs pending or running in op_jobs",
)

archive_queue_length = Gauge(
    "ke_archive_queue_length",
    "Archive jobs pending or running in op_jobs",
)


# ── Record functions ───────────────────────────────────────────────────


def record_compile(*, source: str = "orchestrator") -> None:
    """Registra que se ha solicitado una compilación.

    El contador es en memoria (válido para procesos largos tipo API).
    Para datos históricos persistentes, consultar op_compiler_runs.
    """
    compile_requests.labels(source=source).inc()
    log.debug("Metrics: compile request recorded (source=%s)", source)


def record_search(mode: str = "lexical", duration: float = 0.0) -> None:
    """Registra una búsqueda y su duración."""
    search_requests.labels(mode=mode).inc()
    if duration > 0:
        search_duration.labels(mode=mode).observe(duration)
    log.debug("Metrics: search recorded (mode=%s, duration=%.3f)", mode, duration)


def record_qdrant_sync(operation: str = "upsert", status: str = "done") -> None:
    """Registra una operación de sincronización con Qdrant."""
    qdrant_sync_ops.labels(operation=operation, status=status).inc()
    log.debug("Metrics: qdrant sync recorded (op=%s, status=%s)", operation, status)


def record_archive(kind: str = "source", status: str = "completed") -> None:
    """Registra una operación de archivado."""
    archive_ops.labels(kind=kind, status=status).inc()
    log.debug("Metrics: archive recorded (kind=%s, status=%s)", kind, status)


def record_error(code: str) -> None:
    """Registra un error del Knowledge Engine."""
    errors_total.labels(code=code).inc()
    log.debug("Metrics: error recorded (code=%s)", code)


# ── SQLite helpers ────────────────────────────────────────────────────


def _set_db_gauges(db_path: Path | None) -> None:
    """Actualiza gauges derivados de SQLite.

    Se llama durante export_metrics(). Si la BD no existe o hay error,
    los gauges conservan su último valor conocido.
    """
    if db_path is None or not db_path.exists():
        return
    try:
        conn = open_db(db_path)

        row = conn.execute("SELECT COUNT(*) as c FROM kg_nodes").fetchone()
        db_nodes_total.set(row["c"] if row else 0)

        row = conn.execute("SELECT COUNT(*) as c FROM kg_edges").fetchone()
        db_edges_total.set(row["c"] if row else 0)

        row = conn.execute("SELECT COUNT(*) as c FROM op_compiler_runs").fetchone()
        db_compile_runs.set(row["c"] if row else 0)

        row = conn.execute("SELECT COUNT(*) as c FROM op_compile_errors WHERE severity='ERROR'").fetchone()
        db_compile_errors.set(row["c"] if row else 0)

        row = conn.execute("SELECT COUNT(*) as c FROM op_vector_sync WHERE status IN ('pending', 'failed')").fetchone()
        db_pending_sync.set(row["c"] if row else 0)

        version = conn.execute("PRAGMA user_version").fetchone()
        db_schema_version.set(version[0] if version else 0)

        row = conn.execute(
            "SELECT COUNT(*) as c FROM op_jobs WHERE job_type = 'compile' AND status IN ('pending', 'running')",
        ).fetchone()
        compile_queue_length.set(row["c"] if row else 0)

        row = conn.execute(
            "SELECT COUNT(*) as c FROM op_jobs WHERE job_type = 'archive_source' AND status IN ('pending', 'running')",
        ).fetchone()
        archive_queue_length.set(row["c"] if row else 0)

        conn.close()
    except Exception as exc:
        log.warning("Error leyendo métricas de SQLite: %s", exc)


# ── Export ────────────────────────────────────────────────────────────


def export_metrics(db_path: Path | None = None) -> bytes:
    """Genera output Prometheus OpenMetrics.

    Args:
        db_path: Ruta opcional a knowledge.db para métricas SQLite.
                 Si es None, solo exporta métricas en memoria.

    Returns:
        bytes en formato Prometheus exposition (text/plain; charset=utf-8).

    """
    _set_db_gauges(db_path)
    return generate_latest(REGISTRY)


# ── Reset (tests) ─────────────────────────────────────────────────────


def _reset_for_testing() -> None:
    """Reinicia todos los contadores/gauges. Solo para tests."""
    for collector in list(REGISTRY._collector_to_names):
        if isinstance(collector, Counter | Gauge | Histogram):
            REGISTRY.unregister(collector)
    # Registrar de nuevo
    global search_requests, search_duration, qdrant_sync_ops  # noqa: PLW0603
    global compile_requests, archive_ops, errors_total  # noqa: PLW0603
    global db_nodes_total, db_edges_total, db_compile_runs  # noqa: PLW0603
    global db_compile_errors, db_pending_sync, db_schema_version  # noqa: PLW0603
    global compile_queue_length, archive_queue_length  # noqa: PLW0603
    global audit_write_failures  # noqa: PLW0603
    global compile_lock_wait_seconds, sqlite_busy_retries_total  # noqa: PLW0603
    global job_retry_total, archive_duration_seconds, audit_ingest_duration_seconds  # noqa: PLW0603

    search_requests = Counter("ke_search_requests_total", "", ["mode"])
    search_duration = Histogram("ke_search_duration_seconds", "", ["mode"])
    qdrant_sync_ops = Counter("ke_qdrant_sync_ops_total", "", ["operation", "status"])
    compile_requests = Counter("ke_compile_requests_total", "", ["source"])
    archive_ops = Counter("ke_archive_ops_total", "", ["kind", "status"])
    errors_total = Counter("ke_errors_total", "", ["code"])
    db_nodes_total = Gauge("ke_db_nodes_total", "")
    db_edges_total = Gauge("ke_db_edges_total", "")
    db_compile_runs = Gauge("ke_db_compile_runs_total", "")
    db_compile_errors = Gauge("ke_db_compile_errors_total", "")
    db_pending_sync = Gauge("ke_db_pending_sync", "")
    db_schema_version = Gauge("ke_db_schema_version", "")
    compile_queue_length = Gauge("ke_compile_queue_length", "")
    archive_queue_length = Gauge("ke_archive_queue_length", "")
    audit_write_failures = Counter("ke_audit_write_failures_total", "")
    compile_lock_wait_seconds = Histogram(
        "ke_compile_lock_wait_seconds",
        "",
        buckets=(0.001, 0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0),
    )
    sqlite_busy_retries_total = Counter("ke_sqlite_busy_retries_total", "")
    job_retry_total = Counter("ke_job_retry_total", "", ["job_type", "reason"])
    archive_duration_seconds = Histogram(
        "ke_archive_duration_seconds",
        "",
        buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0),
    )
    audit_ingest_duration_seconds = Histogram(
        "ke_audit_ingest_duration_seconds",
        "",
        buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0),
    )

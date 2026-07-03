-- v8 → v9: Añadir determinism_hash a kg_active_version + tabla op_archives + op_feedback_agg
-- Ver docs/auditoria-integracion-v7.md para contexto.

ALTER TABLE kg_active_version ADD COLUMN determinism_hash TEXT NOT NULL DEFAULT '';

CREATE TABLE IF NOT EXISTS op_archives (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    kind            TEXT NOT NULL CHECK (kind IN ('source', 'vectors', 'cold')),
    source_commit   TEXT,
    manifest_path   TEXT NOT NULL,
    archive_path    TEXT NOT NULL,
    compressed_size INTEGER,
    content_sha256  TEXT NOT NULL,
    archived_at     TEXT NOT NULL DEFAULT (datetime('now')),
    retention_days  INTEGER NOT NULL DEFAULT 90
);

CREATE TABLE IF NOT EXISTS op_feedback_agg (
    doc_id          TEXT PRIMARY KEY,
    n_ratings       INTEGER NOT NULL DEFAULT 0,
    avg_rating      REAL NOT NULL DEFAULT 0.0,
    last_feedback_at TEXT,
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Nota: op_vector_sync.status mantiene 'done' (no 'completed') por compatibilidad
-- con el CHECK constraint existente. op_jobs (cuando se active) usará 'completed'.
-- Decisión documentada en docs/auditoria-integracion-v7.md sección O1.

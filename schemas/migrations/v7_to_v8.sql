-- Migration v7 → v8: op_vector_sync (tracking de sincronización Qdrant)
-- Permite reintentar sincronizaciones fallidas sin perder trazabilidad.
-- run_id vincula cada operación a un compile específico.
-- dead_letter: cuando attempts >= 10 la operación se aborta permanentemente.

CREATE TABLE IF NOT EXISTS op_vector_sync (
    doc_id      TEXT NOT NULL,
    operation   TEXT NOT NULL CHECK (operation IN ('upsert', 'delete')),
    run_id      INTEGER NOT NULL DEFAULT 0,
    status      TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'done', 'failed', 'dead_letter')),
    last_error  TEXT NOT NULL DEFAULT '',
    attempts    INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (doc_id, operation, run_id)
);

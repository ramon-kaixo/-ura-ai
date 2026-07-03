-- v10 → v11: Reemplazar op_audit placeholder por tabla definitiva
--
-- La op_audit original (v8) nunca fue escrita. Es seguro drop + recreate.
-- La nueva tabla tiene columnas para correlation_id, timestamp, metadata
-- y NOT NULL en campos clave para consistencia del NDJSON.

DROP TABLE IF EXISTS op_audit;

CREATE TABLE IF NOT EXISTS op_audit (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    action          TEXT NOT NULL,
    actor           TEXT NOT NULL,
    entity_type     TEXT NOT NULL,
    entity_id       TEXT NOT NULL,
    result          TEXT NOT NULL,
    correlation_id  TEXT NOT NULL DEFAULT '',
    timestamp       TEXT NOT NULL DEFAULT '',
    metadata        TEXT NOT NULL DEFAULT '{}',
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_op_audit_timestamp ON op_audit(timestamp);
CREATE INDEX IF NOT EXISTS idx_op_audit_action ON op_audit(action);

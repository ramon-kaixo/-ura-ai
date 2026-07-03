-- Knowledge Operating System v7 — Schema de base de datos
-- Componentes: kg_* (grafo, reescrito en cada compile) + op_* (operativo, persistente)

-- Migración v6→v7: columna body en kg_nodes (se aplica desde init_db si falla se ignora)

-- ============================================================
-- GRAFO (kg_*) — reescrito en cada compile dentro de BEGIN IMMEDIATE…COMMIT
-- ============================================================

CREATE TABLE IF NOT EXISTS kg_nodes (
    id             TEXT PRIMARY KEY,
    type           TEXT NOT NULL,
    path           TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    frontmatter    TEXT NOT NULL,
    body           TEXT NOT NULL DEFAULT '',
    semantic       TEXT,
    quality        REAL,
    confidence     REAL,
    embed_hash     TEXT,
    updated_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS kg_edges (
    src      TEXT NOT NULL,
    dst      TEXT NOT NULL,
    relation TEXT NOT NULL,
    metadata TEXT,
    PRIMARY KEY (src, dst, relation)
);

CREATE VIRTUAL TABLE IF NOT EXISTS kg_nodes_fts USING fts5(
    id UNINDEXED, title, body, tags,
    tokenize = 'porter unicode61'
);

-- FTS sync is handled manually in the writer (rebuild/delete_ids).
-- No triggers: the FTS5 'delete' merge command has issues in SQLite 3.45.1.

CREATE TABLE IF NOT EXISTS kg_ontology_nodes (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    type       TEXT NOT NULL,
    parent_id  TEXT,
    properties TEXT
);

CREATE TABLE IF NOT EXISTS kg_ontology_edges (
    src      TEXT NOT NULL,
    dst      TEXT NOT NULL,
    relation TEXT NOT NULL,
    PRIMARY KEY (src, dst, relation)
);

CREATE TABLE IF NOT EXISTS kg_active_version (
    singleton         INTEGER PRIMARY KEY CHECK (singleton = 1),
    graph_version     INTEGER NOT NULL,
    source_commit     TEXT NOT NULL,
    compiler_version  TEXT NOT NULL,
    qdrant_collection TEXT NOT NULL DEFAULT '',
    swapped_at        TEXT NOT NULL,
    determinism_hash  TEXT NOT NULL DEFAULT '',
    determinism_algorithm TEXT NOT NULL DEFAULT 'sha256-v1'
);

-- ============================================================
-- OPERATIVO (op_*) — persistente entre compilaciones
-- ============================================================

CREATE TABLE IF NOT EXISTS op_events (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type     TEXT NOT NULL,
    source         TEXT NOT NULL,
    data           TEXT NOT NULL,
    correlation_id TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS op_jobs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    job_type     TEXT NOT NULL,
    priority     INTEGER DEFAULT 0,
    status       TEXT DEFAULT 'pending',
    payload      TEXT,
    dedup_key    TEXT,
    created_at   TEXT NOT NULL,
    started_at   TEXT,
    completed_at TEXT,
    error        TEXT,
    result_data  TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_jobs_dedup ON op_jobs(dedup_key)
    WHERE status IN ('pending', 'running');

CREATE TABLE IF NOT EXISTS op_scheduler (
    job_name  TEXT PRIMARY KEY,
    schedule  TEXT NOT NULL,
    last_run  TEXT,
    next_run  TEXT,
    enabled   INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS op_compiler_runs (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    status            TEXT NOT NULL,
    started_at        TEXT NOT NULL,
    completed_at      TEXT,
    source_commit     TEXT NOT NULL,
    compiler_version  TEXT NOT NULL,
    documents_changed INTEGER DEFAULT 0,
    documents_total   INTEGER DEFAULT 0,
    errors            INTEGER DEFAULT 0,
    warnings          INTEGER DEFAULT 0,
    graph_version     INTEGER,
    details           TEXT
);

CREATE TABLE IF NOT EXISTS op_compile_errors (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      INTEGER,
    error_code  TEXT NOT NULL,
    document    TEXT NOT NULL DEFAULT '',
    stage       TEXT NOT NULL DEFAULT '',
    severity    TEXT NOT NULL DEFAULT 'ERROR',
    message     TEXT NOT NULL DEFAULT '',
    line        INTEGER DEFAULT 0,
    column      INTEGER DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

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

CREATE TABLE IF NOT EXISTS op_audit (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    action          TEXT NOT NULL,
    actor           TEXT NOT NULL,
    entity_type     TEXT NOT NULL,
    entity_id       TEXT NOT NULL,
    result          TEXT NOT NULL,
    correlation_id  TEXT NOT NULL DEFAULT '',
    timestamp       TEXT NOT NULL,
    metadata        TEXT NOT NULL DEFAULT '{}',
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_op_audit_timestamp ON op_audit(timestamp);
CREATE INDEX IF NOT EXISTS idx_op_audit_action ON op_audit(action);
CREATE INDEX IF NOT EXISTS idx_op_jobs_status ON op_jobs(status, job_type);
CREATE INDEX IF NOT EXISTS idx_op_compile_errors_run ON op_compile_errors(run_id);
CREATE INDEX IF NOT EXISTS idx_op_vector_sync_status ON op_vector_sync(status);
CREATE INDEX IF NOT EXISTS idx_op_archives_kind ON op_archives(kind);
CREATE INDEX IF NOT EXISTS idx_feedback_rating ON op_feedback_agg(avg_rating DESC, n_ratings DESC);

-- op_assets: KnowledgeAssets para Capa 11
CREATE TABLE IF NOT EXISTS op_assets (
    id              TEXT PRIMARY KEY,
    asset_type      TEXT NOT NULL,
    metadata        TEXT NOT NULL DEFAULT '{}',
    source          TEXT NOT NULL DEFAULT '{}',
    relationships   TEXT NOT NULL DEFAULT '[]',
    quality         REAL NOT NULL DEFAULT 0.0,
    content_sha256  TEXT,
    wraps           TEXT,
    created_at      TEXT,
    updated_at      TEXT
);
CREATE INDEX IF NOT EXISTS idx_op_assets_type ON op_assets(asset_type);
CREATE INDEX IF NOT EXISTS idx_op_assets_content_sha256 ON op_assets(content_sha256);
CREATE INDEX IF NOT EXISTS idx_op_assets_wraps ON op_assets(wraps);

-- op_lineage: eventos OpenLineage para Capa 11
CREATE TABLE IF NOT EXISTS op_lineage (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type   TEXT NOT NULL,
    event_time   TEXT NOT NULL,
    run_id       TEXT,
    job_name     TEXT,
    namespace    TEXT,
    input_ids    TEXT NOT NULL DEFAULT '[]',
    output_ids   TEXT NOT NULL DEFAULT '[]',
    metadata     TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_op_lineage_run ON op_lineage(run_id);

-- op_governance: políticas de acceso para Capa 11
CREATE TABLE IF NOT EXISTS op_governance (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id    TEXT NOT NULL,
    policy      TEXT NOT NULL,
    actor       TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_op_gov_asset ON op_governance(asset_id);

-- op_memory: memorias persistentes (conversaciones, decisiones, incidents) para Capa 11
CREATE TABLE IF NOT EXISTS op_memory (
    rowid           INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_id       TEXT NOT NULL UNIQUE,
    kind            TEXT NOT NULL,
    title           TEXT NOT NULL,
    content         TEXT NOT NULL DEFAULT '',
    related_assets  TEXT NOT NULL DEFAULT '[]',
    tags            TEXT NOT NULL DEFAULT '[]',
    metadata        TEXT NOT NULL DEFAULT '{}',
    created_at      TEXT,
    updated_at      TEXT
);
CREATE INDEX IF NOT EXISTS idx_op_memory_kind ON op_memory(kind);
CREATE INDEX IF NOT EXISTS idx_op_memory_id ON op_memory(memory_id);

-- ============================================================
-- FASE 7: FTS5 + op_lineage_edges
-- ============================================================

-- op_assets_fts: FTS5 standalone sobre op_assets (extrae title/body desde metadata JSON)
CREATE VIRTUAL TABLE IF NOT EXISTS op_assets_fts USING fts5(
    id UNINDEXED, title, body,
    tokenize = 'unicode61'
);

CREATE TRIGGER IF NOT EXISTS op_assets_fts_ai AFTER INSERT ON op_assets BEGIN
    INSERT INTO op_assets_fts(rowid, id, title, body)
    VALUES (new.rowid, new.id,
            json_extract(new.metadata, '$.title'),
            COALESCE(json_extract(new.metadata, '$.text_preview'), ''));
END;

CREATE TRIGGER IF NOT EXISTS op_assets_fts_ad AFTER DELETE ON op_assets BEGIN
    INSERT INTO op_assets_fts(op_assets_fts, rowid, id, title, body)
    VALUES ('delete', old.rowid, old.id, '', '');
END;

CREATE TRIGGER IF NOT EXISTS op_assets_fts_au AFTER UPDATE ON op_assets BEGIN
    INSERT INTO op_assets_fts(op_assets_fts, rowid, id, title, body)
    VALUES ('delete', old.rowid, old.id, '', '');
    INSERT INTO op_assets_fts(rowid, id, title, body)
    VALUES (new.rowid, new.id,
            json_extract(new.metadata, '$.title'),
            COALESCE(json_extract(new.metadata, '$.text_preview'), ''));
END;

-- op_memory_fts: FTS5 standalone sobre op_memory (usa columnas reales title/content)
CREATE VIRTUAL TABLE IF NOT EXISTS op_memory_fts USING fts5(
    id UNINDEXED, title, content,
    tokenize = 'unicode61'
);

CREATE TRIGGER IF NOT EXISTS op_memory_fts_ai AFTER INSERT ON op_memory BEGIN
    INSERT INTO op_memory_fts(rowid, id, title, content)
    VALUES (new.rowid, new.memory_id, new.title, new.content);
END;

CREATE TRIGGER IF NOT EXISTS op_memory_fts_ad AFTER DELETE ON op_memory BEGIN
    INSERT INTO op_memory_fts(op_memory_fts, rowid, id, title, content)
    VALUES ('delete', old.rowid, old.memory_id, '', '');
END;

CREATE TRIGGER IF NOT EXISTS op_memory_fts_au AFTER UPDATE ON op_memory BEGIN
    INSERT INTO op_memory_fts(op_memory_fts, rowid, id, title, content)
    VALUES ('delete', old.rowid, old.memory_id, '', '');
    INSERT INTO op_memory_fts(rowid, id, title, content)
    VALUES (new.rowid, new.memory_id, new.title, new.content);
END;

-- op_lineage_edges: desnormalizada para queries rápidas de lineage
CREATE TABLE IF NOT EXISTS op_lineage_edges (
    src         TEXT NOT NULL,
    dst         TEXT NOT NULL,
    relation    TEXT NOT NULL,
    event_id    INTEGER REFERENCES op_lineage(id),
    created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_op_lineage_edges_src ON op_lineage_edges(src);
CREATE INDEX IF NOT EXISTS idx_op_lineage_edges_dst ON op_lineage_edges(dst);
CREATE INDEX IF NOT EXISTS idx_op_lineage_edges_pair ON op_lineage_edges(src, dst);
CREATE INDEX IF NOT EXISTS idx_op_lineage_edges_event ON op_lineage_edges(event_id);

-- NOTA: PRAGMAs se aplican por conexión en _get_conn/cli.py (no persistentes aquí)
-- Requeridos: journal_mode=WAL, foreign_keys=ON, synchronous=NORMAL

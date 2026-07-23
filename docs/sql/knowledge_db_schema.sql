CREATE TABLE kg_nodes (
    id             TEXT PRIMARY KEY,
    type           TEXT NOT NULL,
    path           TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    frontmatter    TEXT NOT NULL,
    semantic       TEXT,
    quality        REAL,
    confidence     REAL,
    embed_hash     TEXT,
    updated_at     TEXT NOT NULL
);
CREATE TABLE kg_edges (
    src      TEXT NOT NULL,
    dst      TEXT NOT NULL,
    relation TEXT NOT NULL,
    metadata TEXT,
    PRIMARY KEY (src, dst, relation)
);
CREATE VIRTUAL TABLE kg_nodes_fts USING fts5(
    id UNINDEXED, title, body, tags,
    tokenize = 'porter unicode61'
)
/* kg_nodes_fts(id,title,body,tags) */;
CREATE TABLE IF NOT EXISTS 'kg_nodes_fts_data'(id INTEGER PRIMARY KEY, block BLOB);
CREATE TABLE IF NOT EXISTS 'kg_nodes_fts_idx'(segid, term, pgno, PRIMARY KEY(segid, term)) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS 'kg_nodes_fts_content'(id INTEGER PRIMARY KEY, c0, c1, c2, c3);
CREATE TABLE IF NOT EXISTS 'kg_nodes_fts_docsize'(id INTEGER PRIMARY KEY, sz BLOB);
CREATE TABLE IF NOT EXISTS 'kg_nodes_fts_config'(k PRIMARY KEY, v) WITHOUT ROWID;
CREATE TABLE kg_ontology_nodes (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    type       TEXT NOT NULL,
    parent_id  TEXT,
    properties TEXT
);
CREATE TABLE kg_ontology_edges (
    src      TEXT NOT NULL,
    dst      TEXT NOT NULL,
    relation TEXT NOT NULL,
    PRIMARY KEY (src, dst, relation)
);
CREATE TABLE kg_active_version (
    singleton        INTEGER PRIMARY KEY CHECK (singleton = 1),
    graph_version    INTEGER NOT NULL,
    source_commit    TEXT NOT NULL,
    compiler_version TEXT NOT NULL,
    qdrant_collection TEXT NOT NULL,
    swapped_at       TEXT NOT NULL
);
CREATE TABLE op_events (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type     TEXT NOT NULL,
    source         TEXT NOT NULL,
    data           TEXT NOT NULL,
    correlation_id TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE sqlite_sequence(name,seq);
CREATE TABLE op_audit (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    action       TEXT NOT NULL,
    entity_type  TEXT NOT NULL,
    entity_id    TEXT,
    actor        TEXT,
    hash_before  TEXT,
    hash_after   TEXT,
    result       TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE op_jobs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    job_type     TEXT NOT NULL,
    priority     INTEGER DEFAULT 0,
    status       TEXT DEFAULT 'pending',
    payload      TEXT,
    dedup_key    TEXT,
    created_at   TEXT NOT NULL,
    started_at   TEXT,
    completed_at TEXT,
    error        TEXT
);
CREATE UNIQUE INDEX ux_jobs_dedup ON op_jobs(dedup_key)
    WHERE status IN ('pending', 'running');
CREATE TABLE op_scheduler (
    job_name  TEXT PRIMARY KEY,
    schedule  TEXT NOT NULL,
    last_run  TEXT,
    next_run  TEXT,
    enabled   INTEGER DEFAULT 1
);
CREATE TABLE op_compiler_runs (
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
sqlite_autoindex_kg_edges_1           sqlite_autoindex_kg_ontology_nodes_1
sqlite_autoindex_kg_nodes_1           sqlite_autoindex_op_scheduler_1     
sqlite_autoindex_kg_ontology_edges_1  ux_jobs_dedup                       

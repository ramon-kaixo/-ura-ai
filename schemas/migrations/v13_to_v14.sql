-- Migration v13 → v14: FTS5 + op_lineage_edges + op_jobs.result_data
-- Fase 7 — Optimizaciones de Producción
-- Ver FASE7_DESIGN.md §9 para diseño completo y rollback plan.

-- ============================================================
-- PASO 1: op_assets_fts (standalone, sin content= external)
-- ============================================================
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

-- Backfill (idempotente: DELETE previene duplicados si se re-ejecuta)
DELETE FROM op_assets_fts;
INSERT INTO op_assets_fts(rowid, id, title, body)
SELECT rowid, id,
       json_extract(metadata, '$.title'),
       COALESCE(json_extract(metadata, '$.text_preview'), '')
FROM op_assets;

-- ============================================================
-- PASO 2: op_memory_fts (standalone)
-- ============================================================
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

-- Backfill (idempotente)
DELETE FROM op_memory_fts;
INSERT INTO op_memory_fts(rowid, id, title, content)
SELECT rowid, memory_id, title, content
FROM op_memory;

-- ============================================================
-- PASO 3: op_lineage_edges (desnormalizada)
-- ============================================================
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

-- Backfill desde op_lineage (idempotente: DELETE previene duplicados)
DELETE FROM op_lineage_edges;
INSERT INTO op_lineage_edges(src, dst, relation, event_id, created_at)
SELECT je1.value, je2.value, e.event_type, e.id, e.event_time
FROM op_lineage e,
     json_each(e.input_ids) AS je1,
     json_each(e.output_ids) AS je2;

-- ============================================================
-- PASO 4: op_jobs.result_data
-- ============================================================
ALTER TABLE op_jobs ADD COLUMN result_data TEXT;

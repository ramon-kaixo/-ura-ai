-- Migration v6 → v7: columna body en kg_nodes + FTS sin triggers

ALTER TABLE kg_nodes ADD COLUMN body TEXT NOT NULL DEFAULT '';

-- Remove old FTS triggers; FTS now managed manually by the writer
DROP TRIGGER IF EXISTS kg_nodes_ai;
DROP TRIGGER IF EXISTS kg_nodes_ad;
DROP TRIGGER IF EXISTS kg_nodes_au;

-- Recreate FTS without content= and without triggers
DROP TABLE IF EXISTS kg_nodes_fts;
CREATE VIRTUAL TABLE IF NOT EXISTS kg_nodes_fts USING fts5(
    id UNINDEXED, title, body, tags,
    tokenize = 'porter unicode61'
);

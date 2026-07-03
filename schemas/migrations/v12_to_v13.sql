-- v12 → v13: Extraer content_sha256/wraps a columnas propias + op_memory
--
-- content_sha256 y wraps estaban dentro del JSON metadata.
-- Se extraen a columnas propias para:
--   1. Poder indexarlos y consultarlos eficientemente
--   2. Cumplir con el diseño documentado en CAPA11_INTEGRATION.md
--   3. Preparar el terreno para Fase 6 (backend vectorial)

-- PASO 1: Añadir columnas a op_assets (NULLABLE para no romper código existente)
ALTER TABLE op_assets ADD COLUMN content_sha256 TEXT;
ALTER TABLE op_assets ADD COLUMN wraps TEXT;

-- PASO 2: Backfill desde metadata JSON para datos existentes
UPDATE op_assets SET content_sha256 = json_extract(metadata, '$.content_sha256') WHERE content_sha256 IS NULL;
UPDATE op_assets SET wraps = json_extract(metadata, '$.wraps') WHERE wraps IS NULL;

-- PASO 3: Índices para las nuevas columnas
CREATE INDEX IF NOT EXISTS idx_op_assets_content_sha256 ON op_assets(content_sha256);
CREATE INDEX IF NOT EXISTS idx_op_assets_wraps ON op_assets(wraps);

-- PASO 4: Asegurar tabla op_memory (puede faltar en migraciones incrementales)
-- El schema completo ya la define, pero no tenía archivo de migración propio.
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

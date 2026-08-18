-- Migration v14 → v15: fix triggers FTS5 ('delete' merge command roto en SQLite 3.45.1)
--
-- Problema: los triggers op_assets_fts_ad/au y op_memory_fts_ad/au usaban el
-- comando especial 'delete' de FTS5 con valores vacios, que lanza
-- "SQL logic error" en SQLite 3.45.1 (documentado en knowledge_graph.sql:38
-- para kg_nodes_fts). Consecuencias: delete_asset() fallaba siempre (rollback)
-- y los REPLACE dejaban filas huerfanas/duplicadas en el indice FTS.
--
-- Fix: DELETE por rowid (soportado) + rebuild de ambos indices para limpiar
-- huerfanos acumulados.

DROP TRIGGER IF EXISTS op_assets_fts_ad;
DROP TRIGGER IF EXISTS op_assets_fts_au;

CREATE TRIGGER op_assets_fts_ad AFTER DELETE ON op_assets BEGIN
    DELETE FROM op_assets_fts WHERE rowid = old.rowid;
END;

CREATE TRIGGER op_assets_fts_au AFTER UPDATE ON op_assets BEGIN
    DELETE FROM op_assets_fts WHERE rowid = old.rowid;
    INSERT INTO op_assets_fts(rowid, id, title, body)
    VALUES (new.rowid, new.id,
            json_extract(new.metadata, '$.title'),
            COALESCE(json_extract(new.metadata, '$.text_preview'), ''));
END;

DROP TRIGGER IF EXISTS op_memory_fts_ad;
DROP TRIGGER IF EXISTS op_memory_fts_au;

CREATE TRIGGER op_memory_fts_ad AFTER DELETE ON op_memory BEGIN
    DELETE FROM op_memory_fts WHERE rowid = old.rowid;
END;

CREATE TRIGGER op_memory_fts_au AFTER UPDATE ON op_memory BEGIN
    DELETE FROM op_memory_fts WHERE rowid = old.rowid;
    INSERT INTO op_memory_fts(rowid, id, title, content)
    VALUES (new.rowid, new.memory_id, new.title, new.content);
END;

-- Rebuild op_assets_fts (idempotente): limpia huerfanos de REPLACE/UPDATE rotos
DELETE FROM op_assets_fts;
INSERT INTO op_assets_fts(rowid, id, title, body)
SELECT rowid, id,
       json_extract(metadata, '$.title'),
       COALESCE(json_extract(metadata, '$.text_preview'), '')
FROM op_assets;

-- Rebuild op_memory_fts (idempotente)
DELETE FROM op_memory_fts;
INSERT INTO op_memory_fts(rowid, id, title, content)
SELECT rowid, memory_id, title, content
FROM op_memory;
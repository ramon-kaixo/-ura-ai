-- v9 → v10: Añadir determinism_algorithm a kg_active_version
--
-- Versiona explícitamente el algoritmo del determinism hash
-- para permitir cambios futuros sin romper el histórico.
-- Valor por defecto: 'sha256-v1' (compatible con Fase A/B).

ALTER TABLE kg_active_version ADD COLUMN determinism_algorithm TEXT NOT NULL DEFAULT 'sha256-v1';

# QA Findings — 2026-08-18/19 (TASK-20260818-029, ronda 6)

- **Autor**: [WEB] (OpenCode Web) en ASUS
- **Tarea**: P1.3 cobertura de módulos <80% — `knowledge/engine/asset_store.py` y `knowledge/engine/agent.py`

## Cobertura (antes → después)

| Módulo | Antes | Después | Tests generados | Cobertura medida con |
|---|---|---|---|---|
| `knowledge/engine/asset_store.py` | 19.6% | **100%** | `tests/unit/test_knowledge_asset_store_cobertura.py` (23 tests) | `coverage run --source=knowledge/engine` + `--cov-branch` |
| `knowledge/engine/agent.py` | 41.8% | **100%** | `tests/unit/test_knowledge_agent_cobertura.py` (15 tests) | idem |

## Hallazgo CRÍTICO: triggers FTS5 rotos en SQLite 3.45.1

- **Síntoma**: `delete_asset()` devolvía siempre `False` con `OperationalError: SQL logic error`; `save_asset()` sobre un asset existente (INSERT OR REPLACE) dejaba filas huérfanas/duplicadas en `op_assets_fts` (resultados stale en búsqueda).
- **Causa raíz**: los triggers `op_assets_fts_ad`/`au` y `op_memory_fts_ad`/`au` (creados en `schemas/migrations/v13_to_v14.sql` y replicados en `schemas/knowledge_graph.sql`) usaban el comando especial `'delete'` de FTS5 con valores vacíos. En SQLite 3.45.1 (sistema y `.venv`) ese comando falla SIEMPRE (incluso el ejemplo canónico, verificado empíricamente). El autor ya lo documentó en `knowledge_graph.sql:38` para `kg_nodes_fts` ("sync manual, no triggers") pero la migración v14 lo reincidió para `op_assets_fts` y `op_memory_fts`.
- **Fix** (verificado en memoria + migración E2E): triggers que usan `DELETE FROM <fts> WHERE rowid = old.rowid` (y reinsert en `au`), más rebuild idempotente de ambos índices para limpiar huérfanos.
- **Entrega**: migración `schemas/migrations/v14_to_v15.sql` (aplicable a DBs existentes v14), bump `SCHEMA_VERSION`/`MAXIMUM_SUPPORTED_SCHEMA` 14→15 en `knowledge/engine/migrations.py`, triggers corregidos en `schemas/knowledge_graph.sql` (DBs fresh). Tests: `tests/unit/test_knowledge_migration_v15.py` (4 tests E2E: migración, delete post-migración, limpieza de huérfanos, versionado).

## Verificación

- `pytest tests/unit/test_knowledge_asset_store_cobertura.py tests/unit/test_knowledge_agent_cobertura.py tests/unit/test_knowledge_migration_v15.py` → **42 passed**.
- Tests knowledge/engine (filtro) → **1064 passed, 1 skipped** (0 regresiones con el fix).
- `ruff check` sobre los 6 archivos tocados → All checks passed.
- `mypy --no-incremental` sobre agent/asset_store/migrations → Success, no issues.
- Suite completa `tests/unit` → suite_full11.txt (resultado al cierre).

## Otros hallazgos menores (documentados, no accionados)

- `knowledge/engine/cli/agent.py` (CLI del agente, 24 líneas) sin tests — fuera del alcance de la orden (módulo objetivo era `knowledge/engine/agent.py`). Candidato P1.3 siguiente.
- `Agent._audit_coverage` usa `hasattr(reader, "_db_path")` — guard defensivo inalcanzable con `KnowledgeReader` real (siempre tiene `_db_path`).
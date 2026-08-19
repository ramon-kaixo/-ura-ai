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
## Ronda 7 (2026-08-19): lote feedback/governance/lineage + medición global

| Módulo | Antes | Después | Tests |
|---|---|---|---|
| `knowledge/engine/feedback.py` | 24.8% | **98.1%** | `test_knowledge_feedback_cobertura.py` (24) |
| `knowledge/engine/governance_store.py` | 25.0% | **96.1%** | `test_knowledge_governance_cobertura.py` (14) |
| `knowledge/engine/lineage_store.py` | 20.8% | **95.3%** | `test_knowledge_lineage_cobertura.py` (14) |

### Hallazgo REAL corregido: `_validate_doc_id(None)` crasheaba con TypeError
- `record_feedback(db, None, 3)` / `get_feedback(db, None)` lanzaban `TypeError: object of type 'NoneType' has no len()` en vez de InvalidDocIdError/False/None (el f-string del mensaje evaluaba `len(None)` antes del raise; el except solo capturaba InvalidDocIdError). Fix: guard `if not doc_id` antes de construir el mensaje. Comportamiento observable restaurado (InvalidDocIdError para vacío/None).
- Pre-existente: `# noqa: S608` documentado en `apply_ranking_overlay` (placeholders solo contienen `?`, valores por parámetro).

### Medición global knowledge/engine (sugerencia MEDIA)
- **79.2%** (7592 stmts, 1579 miss) con la selección de tests de knowledge — 0 módulos <80% en esa selección (los módulos con deps externas — vector_ollama/qdrant, extractors web/video/audio/pdf/image/office — no se miden sin servicios).

## Ronda 8 (2026-08-19): markdown/validator/orchestrator/sqlite_writer

| Módulo | Antes | Después | Tests |
|---|---|---|---|
| `knowledge/engine/extractors/markdown.py` | 31.0% | **100%** | `test_knowledge_extractors_markdown_cobertura.py` (21) |
| `knowledge/engine/validator.py` | 34.8% | **100%** | `test_knowledge_validator_cobertura.py` (29) |
| `knowledge/engine/orchestrator.py` | 30.1% | **94.5%** | `test_knowledge_orchestrator_cobertura.py` (9) |
| `knowledge/engine/sqlite_writer.py` | 34.4% | **98.4%** | `test_knowledge_sqlite_writer_cobertura.py` (22) |

- orchestrator: 4 líneas sin cubrir = rutas default (apuntan a prod; intencional no ejecutarlas en tests).
- sqlite_writer: 2 líneas sin cubrir = handler de señal SIGINT/SIGTERM (solo cubribles enviando señal real; el path de rollback por excepción SÍ está cubierto).
- Validado E2E: apply_compile real con schema completo → kg_nodes + kg_edges + FTS + op_compiler_runs + kg_active_version consistentes; rollback ante fallo (0 escrituras).
- **Flaky conocido**: `test_f25_b4_fact_index.py::test_benchmark_lookup_10000` falla ~1 de cada 2 suite completas por carga (10K lookups 206ms > 150ms); aislado pasa (1.28s). Ya marcado flaky en `ea7830a4`. Sin relación con este lote.

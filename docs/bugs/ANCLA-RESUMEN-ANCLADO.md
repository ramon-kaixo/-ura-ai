# RESUMEN ANCLADO — Auditoría Motor de Conocimiento

**Fecha**: 2026-07-01
**Auditoría**: 14 issues detectados en `knowledge/engine/`

## Issues Correjidos

| # | Issue | Archivo | Fix |
|---|-------|---------|-----|
| 1 | `rebuild` en `NodeRepository` — debe ser `INSERT OR REPLACE` | `sqlite_writer.py:118` | `rebuild` → `upsert` usando `INSERT OR REPLACE` |
| 2 | Doble E/S en `scan_incremental()` llama `scan_source()` y `take_snapshot()` | `scanner.py:121` | Snapshot construido desde `scan_source()`; `take_snapshot()` eliminado del flujo incremental |
| 3 | `core/qdrant_client.py` exporta `instancia` como callable (AttributeError) | `core/qdrant_client.py` | Re-export limpio sin instanciación espuria |
| 4 | `compile_source_streaming()` llama `apply_compile` sin `deleted_ids` | `compiler.py:255` | Añadido `deleted_ids=[]` |
| 5 | `_get_qdrant()` llama `MotorQdrant.instancia` sin argumentos | `qdrant_sync.py:34` | Fallback a `UraConfig()` si no hay singleton pre-existente |
| 6 | `sync_documents()` abre conexión SQLite por cada `_track_operation` | `qdrant_sync.py:176` | `_track_conn()` context manager batch; `_track_operation` recibe `conn` |
| 7 | `PRAGMA busy_timeout` duplicado con `_begin_immediate_with_retry` | `sqlite_writer.py:35` | Eliminado `PRAGMA busy_timeout` (redundante con retry loop) |
| 8 | Doble restauración de signal handlers en `_install_cancel_handler` + `_cancel_guard` | `sqlite_writer.py:74` | Handler solo setea flag; `_cancel_guard` restaura en `finally` |
| 9 | `system.tracking_op` en `CompilerRunRepository` | `compiler.py` (no existe) | Código ya no contiene esta variable |
| 10 | `from types import NoneType` en modelos | `models.py` (no existe) | No hay import espurio de NoneType |
| 11 | `embed_hash` inconsistente writer/reader | — | Coinciden ambos lados (`row["embed_hash"]` / `obj.document.embed_hash`) |
| 12 | `scan_incremental` llama `take_snapshot` redundante | `scanner.py` | Corregido en #2 |
| 13 | `new_snapshot.deleted(previous)` llamado por archivo | `scanner.py` | Se llama una vez al final de `scan_incremental` |
| 14 | `_resolve_deleted_ids` recorre deleted para mapear doc_ids | `compiler.py:281` | No se cambió (el mapping es trivial y necesario; id de SourceObject es path relativo, no hash) |

## Próximos pasos
- Verificar lint y tests antes de merge
- Monitorear rendimiento de `scan_incremental` en ASUS

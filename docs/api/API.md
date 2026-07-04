# API — Knowledge Engine v0.2.0

## CLI Commands

```
ke [--db-path PATH] <comando> [args...]
```

### init
| | |
|---|---|
| Descripción | Crea/reset knowledge.db |
| Exit code | 0 = OK, 1 = error |
| `--db-path` | Ruta a knowledge.db (def: ~/URA/ura_ia_1972/knowledge/knowledge.db) |

### compile
| | |
|---|---|
| Descripción | Compila source/ → knowledge.db con flock |
| Exit code | 0 = OK/skipped, 1 = error |
| `--source-dir` | Directorio de origen |
| Protección | flock(2) exclusivo entre procesos |

### status
| | |
|---|---|
| Descripción | Estadísticas del grafo |
| Exit code | 0 |

### search
| | |
|---|---|
| Descripción | Búsqueda full-text |
| Exit code | 0 |
| `query` | Término de búsqueda |
| `--mode` | lexical, hybrid |
| `--type` | Filtro por tipo de documento |
| `--limit` | Máx resultados (def: 10) |

### archive
| | |
|---|---|
| Descripción | Operaciones de archivado |
| Subcomandos: source, list, verify, restore |

#### archive source
| | |
|---|---|
| Crea git bundle + manifest | |
| `--source-dir` | Directorio a archivar |
| `--archive-dir` | Directorio de salida |
| `--retention-days` | Días de retención |

#### archive verify
| | |
|---|---|
| Verifica integridad del archive | |
| `manifest` | Ruta a .manifest.json |
| `--archive-dir` | Directorio permitido |
| Exit code | 0 = OK, 1 = SHA mismatch / no encontrado |

#### archive restore
| | |
|---|---|
| Restaura source desde archive | |
| `manifest` | Ruta a .manifest.json |
| `--dest` | Directorio destino |
| `--archive-dir` | Directorio permitido |

### doctor
| | |
|---|---|
| Health check integral | |
| Exit code | 0 = todo OK, 1 = algún check falló |
| Checks: schema, graph, FTS, migrations, pending sync, qdrant |

### audit-db
| | |
|---|---|
| Auditoría de invariantes de BD | |
| Exit code | 0 = todo OK, 1 = error |
| Checks: integrity_check, orphan edges, active version, stuck jobs, WAL, disco |

### job-process
| | |
|---|---|
| Procesa cola de trabajos | |
| `--source-dir` | Directorio para compile jobs |
| Consumidor: systemd timer |

### rules
| | |
|---|---|
| Evaluación de reglas | |
| Subcomandos: list, eval |

#### rules list
| | |
|---|---|
| Lista reglas definidas | |
| Exit code | 0 |

#### rules eval
| | |
|---|---|
| Evalúa reglas contra documentos | |
| `doc_id` | ID o path (opcional, todos si omite) |
| Exit code | 0 = sin ERROR, 1 = algún ERROR |

### deduce
| | |
|---|---|
| Ejecuta StateDeductor | |
| Exit code | 0 |

## Exit Codes

| Código | Significado |
|---|---|
| 0 | OK |
| 1 | Error general / check falló |

## Schema SQLite (v11)

### Tablas

| Tabla | Propósito | Columnas |
|---|---|---|
| `kg_nodes` | Nodos del grafo | id, type, path, content_sha256, frontmatter, body, semantic, quality, confidence, embed_hash, updated_at |
| `kg_edges` | Aristas del grafo | src, dst, relation, metadata |
| `kg_nodes_fts` | Índice FTS5 (virtual) | id, title, body, tags |
| `kg_active_version` | Versión activa del grafo | singleton, graph_version, source_commit, compiler_version, qdrant_collection, swapped_at, determinism_hash, determinism_algorithm |
| `op_audit` | Auditoría | id, action, actor, entity_type, entity_id, result, correlation_id, timestamp, metadata, created_at |
| `op_jobs` | Cola de trabajos | id, job_type, priority, status, payload, dedup_key, created_at, started_at, completed_at, error |
| `op_compiler_runs` | Historial de compilaciones | id, status, started_at, completed_at, source_commit, compiler_version, documents_changed, documents_total, errors, warnings, graph_version, details |
| `op_compile_errors` | Errores de compilación | id, run_id, error_code, document, stage, severity, message, line, column, created_at |
| `op_vector_sync` | Tracking de sync Qdrant | doc_id, operation, run_id, status, last_error, attempts, created_at, updated_at |
| `op_archives` | Registro de archives | id, kind, source_commit, manifest_path, archive_path, compressed_size, content_sha256, archived_at, retention_days |

### PRAGMAs obligatorios
| PRAGMA | Valor |
|---|---|
| journal_mode | WAL |
| foreign_keys | ON |
| synchronous | NORMAL |
| journal_size_limit | 67108864 |
| busy_timeout | 5000 |

### Índices actuales
| Índice | Tabla | Columnas |
|---|---|---|
| ux_jobs_dedup | op_jobs | dedup_key (WHERE status IN ('pending','running')) |
| idx_op_audit_timestamp | op_audit | timestamp |
| idx_op_audit_action | op_audit | action |

## Formato NDJSON (Auditoría)

Una línea por evento, UTF-8, LF:

```json
{"action": "search", "actor": "reader", "entity_type": "graph",
 "entity_id": "query...", "result": "success",
 "correlation_id": "abc123", "timestamp": "2026-01-01T00:00:00",
 "metadata": {"docs_returned": 3}}
```

Rotación: audit.ndjson → .ndjson.1 → .ndjson.2 (100 MB por segmento, máx 3).

## Formato Manifest (Archive)

```json
{"version": "1.0", "kind": "source", "source_commit": "abc...",
 "created_at": "20260101_120000_123456", "archive_path": "/path/to/bundle",
 "compressed_size": 1024, "content_sha256": "abc...",
 "file_count": 10, "retention_days": 90}
```

## Reglas (R001-R005)

| ID | Versión | Severidad | Costo | Descripción |
|---|---|---|---|---|
| R001 | 1 | WARN | O(1) | Documento sin título |
| R002 | 1 | INFO | O(1) | Documento sin tags |
| R003 | 1 | WARN | O(1) | Documento sin body |
| R004 | 1 | ERROR | O(n) | Enlace a nodo inexistente |
| R005 | 1 | INFO | O(1) | Documento huérfano |

## API Pública (congelada)

Solo estos módulos y funciones forman parte de la API pública.
Todo lo demás es interno y puede cambiar sin previo aviso.

### `knowledge.engine`

| Función/Módulo | Propósito | Excepciones |
|---|---|---|
| `compile_source()` | Compila source/ → knowledge.db | `CompileError`, `ValidationError`, `LockAcquisitionError` |
| `request_compile()` | Solicita compilación con flock | `LockAcquisitionError`, `OSError` |
| `KnowledgeReader` | Búsqueda y lectura del grafo | `ValueError` (modo inválido), `sqlite3.OperationalError` |
| `RuleEvaluator` | Evaluación de reglas | `UnsafeExpressionError`, `TimeoutError` |
| `StateDeductor` | Deducción de estado | Ninguna (best-effort) |
| `archive_source()` | Crear git bundle | `ValueError` (no es git), `RuntimeError` (bundle) |
| `verify_archive()` | Verificar integridad | `PathTraversalError` |
| `restore_source()` | Restaurar desde archive | `ValueError`, `FileNotFoundError`, `PathTraversalError` |
| `AuditService` | Servicio de auditoría | Ninguna (best-effort, nunca raise) |
| `NDJSONAuditBackend` | Backend NDJSON | Ninguna (best-effort) |
| `SQLiteAuditBackend` | Backend SQLite | Ninguna (best-effort) |
| `Pipeline` | Pipeline DAG | Ninguna (resultados en StageResult) |
| `Agent` (Protocol) | Framework de agentes | Ninguna |

### Módulos internos (NO usar directamente)
```
knowledge.engine.sqlite_writer
knowledge.engine.qdrant_sync
knowledge.engine.scanner
knowledge.engine.parser
knowledge.engine.validator
knowledge.engine.knowledge_verifier
knowledge.engine.storage_verifier
knowledge.engine.lock
knowledge.engine.jobs
```

## Invariantes (congelados)

Ver `docs/architecture/INVARIANTS.md` para los 10 invariantes arquitectónicos.

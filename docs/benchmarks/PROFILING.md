# Perfilado — Knowledge Engine v0.2.0

**Fecha:** 2026-07-01
**Sistema:** Linux, Python 3.12.3
**Método:** cProfile

## Compile (50 documentos)

| Función | Tiempo acumulado | % |
|---|---|---|
| `compile_source` | 9ms | 100% |
| `apply_compile` | 5ms | 55% |
| `scan_incremental` / `scan_source` | 4ms | 45% |
| `sqlite3.commit` | 1ms | 11% |

**Cuello de botella:** `pathlib.relative_to` (2ms, 22%) — llamado 50 veces (una por documento).
**Observación:** Compile es extremadamente rápido. El tiempo está dominado por I/O de SQLite.

## Search (100 queries)

| Función | Tiempo acumulado | % |
|---|---|---|
| `search` / `_search_lexical` | 20ms | 100% |
| `sqlite3.execute` | 14ms | 70% |
| `open_db` (PRAGMAs) | 13ms | 65% |
| `sqlite3.connect` | 2ms | 10% |

**Cuello de botella:** `open_db` se llama 100 veces (una por búsqueda). Cada conexión ejecuta 5 PRAGMAs.
**Recomendación:** Reutilizar conexiones SQLite para búsquedas múltiples (connection pool o singleton por proceso).

## Recomendaciones

| Área | Impacto | Acción |
|---|---|---|
| Search: conexiones no reutilizadas | Alto | Usar connection pool en KnowledgeReader |
| Compile: pathlib.relative_to | Bajo | 22% de 9ms no es crítico |
| General: SQLite WAL checkpoint | Medio | Monitorear crecimiento WAL en stress largo |

## Línea base (para detectar regresiones)

| Operación | Carga | Tiempo |
|---|---|---|
| Compile | 50 docs | ~9ms |
| Search (lexical) | 100 queries | ~20ms |
| Search por query | 1 query | ~0.2ms |

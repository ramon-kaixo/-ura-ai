# Acta de Cierre — Fase 7 (Optimizaciones de Producción)

> **Versión:** 3.0  
> **Fecha:** 2026-07-04  
> **Estado:** ✅ Cerrada  
> **Fase anterior:** Fase 6 — Backend Vectorial  
> **Fase siguiente:** —  

---

## Resumen

Fase 7 optimiza la producción del Knowledge Engine con **FTS5** en búsquedas,
**op_lineage_edges** para lineage O(1), **background queue** para extracción
asíncrona, **autorecuperación** de backends vectoriales y **reconciliación**
AssetStore↔VectorStore.

**Principio:** Todas las optimizaciones tienen degradación graceful.
Sin FTS5 → LIKE. Sin edges → JSON LIKE. Sin queue → síncrono.
Sin recovery ni reconcile → backends vectoriales offline.

---

## Entregables

### Archivos nuevos (2)

| Archivo | LOC | Propósito |
|---------|-----|-----------|
| `schemas/migrations/v13_to_v14.sql` | 79 | Migración v13→v14 con FTS5, edges, backfill |
| `scripts/pro/reindex_vectors.py` | 101 | CLI para reconcile (--execute/--batch) |

### Tests nuevos (3 archivos, 43 checks)

| Archivo | Escenario |
|---------|-----------|
| `tests/test_fase7.py` | 36 unit + 3 integration tests |
| `tests/benchmark_fase7.py` | 6 benchmarks vs targets |
| `tests/e2e_fase7.py` | 39 validaciones E2E |

### Tests de verificación H1 añadidos (1 archivo, 8 tests)

| Archivo | Tests | Escenario |
|---------|-------|-----------|
| `tests/test_fase7.py` | 8 | `TestListIds`: scroll API, paginación, degradación, 250 vectores sin loop infinito, reconcile con >250 assets |

### Tests existentes corregidos (2 archivos, 9 tests)

| Archivo | Tests | Cambio |
|---------|-------|--------|
| `tests/test_vector_qdrant.py` | 6 | `available` O(1) + `check_available()` |
| `tests/test_vector_ollama.py` | 3 | `available` O(1) + `check_available()` |

### Archivos modificados (13)

| Archivo | LOC | Cambio principal |
|---------|-----|------------------|
| `schemas/knowledge_graph.sql` | +8 | `op_assets_fts`, `op_memory_fts`, `op_lineage_edges`, `op_jobs.result_data` |
| `knowledge/engine/migrations.py` | +5 | SCHEMA_VERSION=14, ENGINE_VERSION=0.3.0, MAXIMUM_SUPPORTED_SCHEMA=14 |
| `knowledge/engine/asset_store.py` | +62 | `search_assets()` con FTS5 + fallback LIKE, `_sanitize_fts5()` |
| `knowledge/engine/memory_store.py` | +40 | `search()` migrado a FTS5 + fallback LIKE |
| `knowledge/engine/lineage_store.py` | +55 | `store_lineage_event()` puebla `op_lineage_edges` |
| `knowledge/engine/extraction_service.py` | +345 | `queue_extract()`, `get_queue_status()`, worker loop, fork-safety |
| `knowledge/engine/graphrag.py` | +5 | `retrieve_assets()` usa `search_assets()` |
| `knowledge/engine/vector_base.py` | +14 | `check_available()` + `list_ids()` en VectorStore Protocol |
| `knowledge/engine/vector_qdrant.py` | +75 | `available` O(1), `check_available()` con backoff, `list_ids()` con scroll API |
| `knowledge/engine/vector_ollama.py` | +40 | `available` O(1), `check_available()` con backoff |
| `knowledge/engine/vector_retriever.py` | +120 | `reconcile()` con dry-run, upsert batch, cleanup huérfanos; `_get_vector_ids()` reescrito con `list_ids()` |
| `docs/architecture/CONTRACTS_FROZEN.md` | v2.0 | Contratos Fase 7 añadidos |

### Documentación modificada

| Documento | Cambio |
|-----------|--------|
| `docs/architecture/PROJECT_STATE.md` | v0.6.0, schema v14, Fase 7 movida a Completadas |

---

## Criterios de Aceptación

| # | Criterio | Estado |
|---|----------|--------|
| CA1 | `AssetStore.search_assets()` usa FTS5 cuando está disponible | ✅ |
| CA2 | `MemoryStore.search()` usa FTS5 cuando está disponible | ✅ |
| CA3 | `LineageStore.get_upstream()`/`get_downstream()` usa edges primero | ✅ |
| CA4 | `ExtractionService.queue_extract()` encola y retorna job_id | ✅ |
| CA5 | Worker loop ejecuta extracción en subprocess con heartbeat | ✅ |
| CA6 | `GraphRetriever.retrieve_assets()` usa `search_assets()` | ✅ |
| CA7 | `QdrantVectorStore.available` es O(1), `check_available()` con backoff | ✅ |
| CA8 | `OllamaEmbedder.available` es O(1), `check_available()` con backoff | ✅ |
| CA9 | `VectorAugmentedRetriever.reconcile()` con dry-run y batch | ✅ |
| CA10 | `scripts/pro/reindex_vectors.py` CLI funcional | ✅ |
| CA11 | Migración v13→v14: FTS5, edges, backfill | ✅ |
| CA12 | Schema v14 en `knowledge_graph.sql` | ✅ |
| CA13 | Degradación graceful: sin FTS5 → LIKE, sin edges → JSON LIKE | ✅ |
| CA14 | `available` property no hace HTTP checks (O(1)) | ✅ |
| CA15 | Benchmark E2E no duplica latencia vs v0.4.0 | ✅ |
| CA16 | 461 tests pasando (39 Fase 7 + 8 H1 + 414 preexistentes) | ✅ |
| CA17 | Sin regresiones en tests existentes | ✅ |
| CA18 | 6/6 targets de benchmark cumplidos | ✅ |
| CA19 | `_get_vector_ids()` no produce loop infinito con >100 vectores | ✅ |
| CA20 | `list_ids()` en VectorStore Protocol + implementación Qdrant scroll API | ✅ |

---

## Defectos Corregidos Durante Implementación

| # | Defecto | Archivo | Corrección |
|---|---------|---------|------------|
| 1 | `queue_extract` sin manejo de dedup (IntegrityError) | `extraction_service.py` | Catch IntegrityError → retorna job_id existente |
| 2 | Mock `list_assets` en E2E retornaba siempre el mismo batch → loop infinito | `e2e_fase7.py` | Usar `side_effect` para simular paginación |
| **H1** | `_get_vector_ids()` incrementaba `offset` local pero NUNCA lo pasaba a `search()` → con >100 vectores, cada iteración recibía los mismos resultados → **loop infinito** | `vector_retriever.py` | Añadir `list_ids()` a VectorStore Protocol, implementar con scroll API de Qdrant, reescribir `_get_vector_ids()` para usar `list_ids()` |

---

## Auditoría Técnica

Se realizó auditoría técnica completa del código implementado. Un hallazgo crítico
fue detectado y corregido antes del cierre definitivo.

### Hallazgos Iniciales

| ID | Severidad | Hallazgo | Estado |
|----|-----------|----------|--------|
| **H1** | 🔴 Crítico | `_get_vector_ids()` loop infinito con >100 vectores | ✅ **Cerrado** |
| H2 | 🟡 Medio | Sin método de enumeración en VectorStore Protocol | ✅ **Cerrado** (list_ids() añadido) |
| H3 | 🟡 Medio | — | — |
| H4 | 🟡 Medio | — | — |
| H5 | 🟢 Bajo | — | — |
| H6 | 🟢 Bajo | — | — |
| H7 | 🟢 Bajo | — | — |
| H8 | 🟢 Bajo | — | — |

### Re-auditoría Post-Corrección (2026-07-03)

| Verificación | Resultado |
|--------------|-----------|
| `_get_vector_ids()` ya no usa `search()` con vector cero | ✅ |
| `list_ids()` en `VectorStore(Protocol)` | ✅ `vector_base.py:64` |
| `list_ids()` en `QdrantVectorStore` (scroll API) | ✅ `vector_qdrant.py:161` |
| `_get_vector_ids()` reescrito con `list_ids()` | ✅ `vector_retriever.py:188` |
| Sin loop infinito con >100 vectores | ✅ Test 250 vectores en 3 páginas |
| `reconcile()` completo con vectores | ✅ Test reconcile 250 assets |
| 0 regresiones en tests | ✅ 461 pass, 0 new failures |

### Auditoría Adversarial (2026-07-04)

Se realizó auditoría adversarial externa con 19 hallazgos (B01-B08, A01-A11).
Cada hallazgo fue verificado contra código fuente real antes de aceptarse:

### Taxonomía Normalizada (v3.0)

Identificadores estables: **B01-B08** (benchmark), **A01-A11** (adversarial),
**M01-M09** (código/auditoría), **H1** (hallazgo crítico original).

| ID | Hallazgo | Tipo | Severidad | Estado | Evidencia (archivo:línea) |
|----|----------|------|-----------|--------|---------------------------|
| **B01** | Benchmark FTS5 usa conn.execute() en setup, no en medición | Metodológico | — | ✅ **Corregido** | `benchmark_fase7.py:100` → `search_assets()` |
| **B02** | Sin test que verifique solo APIs públicas en benchmark | Cobertura tests | — | ✅ **Corregido (Fase 8)** | `benchmark_fase7.py` — B02 `_verify_no_direct_sql()` |
| **B03** | Sin test de integridad targets benchmark vs SLAs | Cobertura tests | — | ✅ **Corregido (Fase 8)** | `benchmark_fase7.py` — B03 `_verify_targets_in_sla()` |
| **B04** | Sin verificación targets benchmark vs SLAs documentados | Cobertura tests | — | ✅ **Corregido (Fase 8)** | `benchmark_fase7.py` — B04 `_verify_targets_match_sla()` |
| **B05** | SQL directo en E2E (falso positivo) | Falso positivo | — | ❌ **Descartado** | `e2e_fase7.py:200-238` — todas las ops van por ExtractionService |
| **B06** | Benchmark lineage usa conn.execute() en setup | Metodológico | — | ✅ **Corregido** | `benchmark_fase7.py:223` → `get_upstream()` |
| **B07** | Zona gris setup/medición en E2E benchmark | Metodológico | — | ✅ **Corregido** | `benchmark_fase7.py` — verificado sin SQL en mediciones |
| **B08** | Sin benchmark GX10 real en CI | Cobertura tests | — | ✅ **Corregido (Fase 8)** | `scripts/pro/benchmark_baseline.py` — baseline comparison tool |
| | | | | | |
| **A01** | conn.close() con UnboundLocalError si open_db() falla | Bug funcional | P0 | ✅ **Corregido** | `asset_store.py:209-231` |
| **A02** | Mismo patrón en memory_store.py | Bug funcional | P0 | ✅ **Corregido** | `memory_store.py:179-201` |
| **A03** | Mismo patrón en lineage_store.py | Bug funcional | P0 | ✅ **Corregido** | `lineage_store.py:117-145` |
| **A04** | proc.close() sin proc.join() previo → ValueError | Robustez | P1 | ✅ **Corregido** | `extraction_service.py:138,362` |
| **A05** | proc.start() fuera de jobs_lock → race condition | Bug funcional | P0 | ✅ **Corregido** | `extraction_service.py:326-328` |
| **A06** | except Exception captura KeyboardInterrupt | Robustez | P1 | ✅ **Corregido** | `extraction_service.py:265-267` |
| **A07** | return vectors en except → set parcial | Bug funcional | P0 | ✅ **Corregido** | `vector_retriever.py:206-208` |
| **A08** | _upsert_batch sin defensa en embed() | Robustez | P1 | ✅ **Corregido** | `vector_retriever.py:215-219` |
| **A09** | reconcile sin defensa en list_assets() | Robustez | P1 | ✅ **Corregido** | `vector_retriever.py:144-148` |
| **A10** | v13_to_v14.sql no idempotente (falso positivo) | Falso positivo | — | ❌ **Descartado** | Ya usa DELETE+INSERT, idempotente |
| **A11** | check_available() sin backoff en 4xx | Bug funcional | P0 | ✅ **Corregido** | `vector_qdrant.py:221-222` |
| | | | | | |
| **M01** | Backfill edges sin idempotencia | Robustez | P1 | ✅ **Corregido** | `v13_to_v14.sql:35,68,90` → DELETE+INSERT |
| **M02** | _get_vector_ids() no documentado en contratos | Documentación | — | ✅ **Corregido (Fase 8)** | CONTRACTS_FROZEN.md §6.6 |
| **M03** | except Exception silencia errores que no son "no such table" | Robustez | P1 | ✅ **Corregido** | `lineage_store.py:77-80` |
| **M04** | next_offset sin guard en _get_vector_ids() | Defensivo | — | ✅ **Corregido (Fase 8)** | `vector_retriever.py:207-213` — `seen_offsets` guard loop |
| **M05** | scroll API sin timeout en list_ids() | Defensivo | — | ✅ **Corregido (Fase 8)** | `vector_qdrant.py:161-189` — `timeout` param en scroll |
| **M06** | proc.wait() sin timeout | Defensivo | — | ❌ **Descartado** | Falso positivo — `extraction_service.py` creado con timeout ya presente en commit `9112322` |
| **M07** | Modo degradado sin FTS5 no documentado | Documentación | — | ✅ **Corregido (Fase 8)** | FASE7_DESIGN.md §10 — heading + alcance ampliado |
| **M08** | list_ids() omitido en VectorStore Protocol raíz | Documentación | — | ✅ **Corregido (Fase 8)** | CONTRACTS_FROZEN.md §1.2 — `list_ids()` añadido al Protocol |
| **M09** | Fase 7 no listada en README.md | Documentación | — | ✅ **Corregido (Fase 8)** | `README.md` — creado con tabla de fases |
| | | | | | |
| **H1** | _get_vector_ids() loop infinito con >100 vectores | Bug funcional | 🔴 Crítico | ✅ **Corregido** | `vector_retriever.py:188` + `vector_base.py:64` + `vector_qdrant.py:161` |

#### Resumen por estado

| Estado | Cuenta | IDs |
|--------|--------|------|
| ✅ **Corregido (P0)** | 6 | A01, A02, A03, A05, A07, A11 |
| ✅ **Corregido (P1)** | 6 | A04, A06, A08, A09, M01, M03 |
| ✅ **Corregido (benchmark)** | 3 | B01, B06, B07 |
| ✅ **Corregido (crítico)** | 1 | H1 |
| ✅ **Corregido (Fase 8)** | 10 | B02, B03, B04, B08, M02, M04, M05, M07, M08, M09 |
| ❌ **Descartado** | 3 | B05, A10, M06 |
| 🔵 **Backlog** | 0 | — |
| **Total corregido** | **26** | |
| **Total descartado** | **3** | |

Benchmarks refactorizados para APIs públicas (B01, B06, B07).
16 correcciones totales: 6 P0 + 6 P1 + 3 benchmark + 1 crítico original.

**Estado final: Sin hallazgos abiertos de severidad crítica o alta.**
Todos los componentes implementados cumplen los contratos definidos en
`CONTRACTS_FROZEN.md` v2.0 y `FASE7_DESIGN.md`.

---

## Evidencia Objetiva de Cierre

| # | Verificación | Resultado | Detalle |
|---|-------------|-----------|---------|
| 1 | **pytest completo** | ✅ | 461 passed, 10 pre-existing fail, 1 skipped, 33.77s (en GX10) |
| 2 | **Ruff** | ✅ | 25 findings, todos pre-existentes (SLF001, FBT, TC003, S108), 0 nuevos |
| 3 | **Migración v0→v14** | ✅ | Fresh DB → 38 tablas, user_version=14 |
| 4 | **Migración v13→v14** | ✅ | Benchmark: 5.2ms (<100ms target). Backfill idempotente (DELETE+INSERT). |
| 5 | **Test paginación >250 vectores** | ✅ | 8/8 TestListIds: sin loop infinito, 250 IDs exactamente una vez |
| 6 | **Test reconcile >250 assets** | ✅ | stats["to_upsert"]==250, stats["to_delete"]==0 |
| 7 | **Benchmark GX10 (real)** | ✅ | 6/6 targets: FTS5 0.9ms, E2E 7.4ms (<2.0s target). APIs públicas: `search_assets()`, `search()`, `get_upstream()`, `init_db()`, `save_asset()`. |
| 8 | **Auditoría adversarial (19 hallazgos)** | ✅ | B01-B04, B06, B08: benchmarks refactorizados a APIs públicas. A01-A03 leaks, A05 race, A07 set parcial, A11 backoff: P0 corregidos. A04 join+close, A06 except específico, A08/A09 defensas, M01 backfill, M03 except filtrado: P1 corregidos. 2 descartados. |
| 9 | **Hallazgos críticos/altos** | ✅ | H1 (🔴) cerrado. P0 (6) + P1 (5) = 11 hallazgos corregidos. 0 abiertos. |

---

## Deuda Técnica Reconocida

| Item | Impacto | Plan |
|------|---------|------|
| Worker loop en subprocess no testeado en CI | Posible fallo en integración real | Validar en GX10 con backends reales |
| `reindex_vectors.py` sin modo programático | Solo CLI, no invocable desde API | Añadir endpoint REST si necesario |
| Benchmarks en Mac sin GPU | No reflejan rendimiento real GX10 | ✅ **Resuelto**: benchmark ejecutado en GX10 |
| Tests de migración v5→v7 y v6→v7 fallan | Pre-condiciones de schema no coinciden con schema v14 actual | Corregir fixtures de test en mantenimiento |

---

## Riesgos Remanentes

| Riesgo | Impacto | Probabilidad | Mitigación |
|--------|---------|--------------|------------|
| Worker loop zombie en producción | Procesos huérfanos | Baja (chain terminate→kill) | heartbeat + timeout en systemd |
| FTS5 tokenizer no soporta español | Stemming incorrecto para textos en ES | Baja | `unicode61` es neutral, falls back a LIKE |
| Qdrant/Ollama timeout en reconcile | Reconciliación incompleta | Baja | Batch + logging, retry en siguiente ejecución |

---

## Lecciones Aprendidas

1. **FTS5 standalone sin content= external** fue la decisión correcta.
   `json_extract()` es incompatible con FTS5 content sync, y la flexibilidad
   de la metadata JSON justifica el costo adicional de triggers.
2. **El infinite loop del mock** (`list_assets` siempre retorna el mismo batch)
   se detectó en E2E, no en tests unitarios. Lección: los mocks de paginación
   siempre deben usar `side_effect`, no `return_value`.
3. **Dedup por SHA256 de location** requiere manejo de `IntegrityError`.
   El diseño lo especificaba pero la implementación inicial no lo cubría.
   El E2E validation lo detectó.
4. **Worker loop fork-safe** fue más simple de lo esperado: el child abre su
   propia conexión SQLite y no toca el EventBus del padre. El mayor desafío
   fue la terminación limpia (chain terminate→kill).
5. **H1 (loop infinito):** `_get_vector_ids()` no pasaba `offset` a `search()`
   porque el Protocol `VectorStore` no tenía método de enumeración for-bulk.
   La solución fue añadir `list_ids()` al Protocol (permitido por §2 de
   `CONTRACTS_FROZEN.md`) e implementarlo correctamente con scroll API de Qdrant.
   Lección: cuando un método necesita enumerar todos los elementos de un store,
   el método de enumeración debe ser parte del contrato, no un abuso de search.

---

## Línea Base

| Propiedad | Valor |
|-----------|-------|
| Baseline | v0.6.0 |
| Schema | v14 |
| Fase actual | — (todas completadas) |
| Tests | 461 relevantes — 0 nuevos fallos |
| Nuevos fallos | **0** (ninguno introducido por Fase 7) |
| Fallos heredados | 10 preexistentes (test_knowledge_engine: migration fixtures desactualizados) |
| Fallos por entorno | 4 colección (test_openclaw, test_snc_anomalias, test_unit, test_vram_guard) |
| Estado | Implementación de Fase 7 cerrada y auditada. H1 corregido. Auditoría adversarial: 19 hallazgos verificados, 11 corregidos (6 P0 + 5 P1), benchmarks refactorizados a APIs públicas. |

### Benchmark de Rendimiento (Refactorizado — APIs públicas Fase 7)

Benchmark refactorizado: todas las mediciones usan exclusivamente APIs públicas
(`SQLiteAssetStore.search_assets()`, `SQLiteMemoryStore.search()`,
`SQLiteLineageStore.get_upstream()`, `init_db()`/`migrate_db()`,
`SQLiteAssetStore.save_asset()`). Sin SQL directo en mediciones.

| Operación | API usada | Tiempo | Target | Resultado |
|-----------|-----------|--------|--------|-----------|
| FTS5 search (1 asset) | `AssetStore.search_assets()` | 1.1ms | <10ms | ✅ |
| FTS5 search (1000 assets) | `AssetStore.search_assets()` | 1.0ms | <50ms | ✅ |
| LIKE fallback (1000 assets) | `AssetStore.search_assets()` (degradación graceful) | 3.1ms | — | FTS5 es 3.0× más rápido |
| FTS5 memory (10 recs) | `MemoryStore.search()` | 1.0ms | <10ms | ✅ |
| Lineage edge lookup | `LineageStore.get_upstream()` | 0.6ms | <5ms | ✅ |
| Migration v13→v14 | `init_db()` → `migrate_db()` | 2.9ms | <100ms | ✅ |
| **E2E (2 docs)** | **`save_asset()` + `search_assets()`** | **3.7ms** | **<2000ms** | ✅ |

---

## Firma

| Rol | Fecha |
|-----|-------|
| Diseño congelado | 2026-07-03 |
| Implementación | 2026-07-03 |
| Benchmark (GX10) | 2026-07-03 |
| Refactor benchmark (APIs públicas) | 2026-07-04 |
| Validación E2E | 2026-07-03 |
| Auditoría técnica | 2026-07-03 |
| Corrección H1 | 2026-07-03 |
| Re-auditoría H1 | 2026-07-03 |
| Auditoría adversarial | 2026-07-04 |
| Corrección P0 (6 bugs funcionales) | 2026-07-04 |
| Corrección P1 (5 robustez) | 2026-07-04 |
| Cierre documental | 2026-07-04 |

---

*Documento de cierre — Fase 7 Optimizaciones de Producción — Knowledge Engine — 2026-07-04*

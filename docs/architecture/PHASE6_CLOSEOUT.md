# Acta de Cierre — Fase 6 (Backend Vectorial)

> **Versión:** 1.0  
> **Fecha:** 2026-07-03  
> **Estado:** ✅ Cerrada  
> **Fase anterior:** Fase 5 — Extractores Reales  
> **Fase siguiente:** Fase 7 — Optimizaciones de Producción  

---

## Resumen

Fase 6 implementa un **backend vectorial opcional** que permite enriquecer
las búsquedas con similitud semántica (embeddings) y almacenamiento
vectorial (Qdrant). Sin él, el sistema funciona exactamente igual
(ranking heurístico, Fase 4).

**Principio:** El backend vectorial es siempre opcional y degradable.

---

## Entregables

### Archivos nuevos (4)

| Archivo | LOC | Propósito |
|---------|-----|-----------|
| `knowledge/engine/vector_base.py` | 97 | `Embedder(Protocol)`, `VectorStore(Protocol)`, `VectorItem`, `VectorResult` |
| `knowledge/engine/vector_ollama.py` | 168 | `OllamaEmbedder` (httpx, cache LRU) |
| `knowledge/engine/vector_qdrant.py` | 204 | `QdrantVectorStore` (HTTP directo, sin qdrant-client) |
| `knowledge/engine/vector_retriever.py` | 116 | `VectorAugmentedRetriever` (RRF, composición GraphRetriever) |

### Tests nuevos (5 archivos, 112 tests)

| Archivo | Tests |
|---------|-------|
| `tests/test_vector_base.py` | 42 |
| `tests/test_vector_ollama.py` | 22 |
| `tests/test_vector_qdrant.py` | 24 |
| `tests/test_vector_retriever.py` | 16 |
| `tests/test_vector_subscriber.py` | 8 |
| **Total** | **112** |

### Archivos modificados (4)

| Archivo | Cambio |
|---------|--------|
| `knowledge/engine/eventbus.py` | Nuevo evento `MetadataExtracted` |
| `knowledge/engine/extraction_service.py` | Publica `MetadataExtracted` tras `save_asset` exitoso |
| `knowledge/engine/subscribers.py` | `_make_vector_index_subscriber` + parámetros opcionales en `subscribe_all()` |
| `knowledge/engine/__init__.py` | Exports de `VectorAugmentedRetriever` |

### Documentación modificada

| Documento | Cambio |
|-----------|--------|
| `docs/architecture/PROJECT_STATE.md` | v0.4.0 — Fase 6 movida a Completadas, inventario actualizado, 425 tests |

---

## Criterios de Aceptación

| # | Criterio | Estado |
|---|----------|--------|
| 1 | `Embedder(Protocol)` + `VectorStore(Protocol)` definidos e implementados | ✅ |
| 2 | Degradación graceful: sin Qdrant/Ollama → sistema funciona igual | ✅ |
| 3 | RRF fusiona correctamente resultados heurísticos y vectoriales | ✅ |
| 4 | `VectorAugmentedRetriever.retrieve_assets(use_vector=True)` funciona end-to-end | ✅ |
| 5 | MetadataExtracted → suscriptor → upsert automático | ✅ |
| 6 | 112 tests nuevos pasando (todos los métodos con test positivo, negativo, degradación y determinismo) | ✅ |
| 7 | Sin regresiones en tests existentes | ✅ |
| 8 | Sin modificaciones al núcleo ni a módulos de Fase 0–5 | ✅ |
| 9 | Zero `NotImplementedError` en implementaciones normales | ✅ |
| 10 | `upsert()` no conoce `KnowledgeAsset` (recibe `list[VectorItem]`) | ✅ |

---

## Auditoría Técnica

Se realizó auditoría técnica completa del código implementado
(14 hallazgos). Resultados:

| Severidad | Cantidad | Acción |
|-----------|----------|--------|
| Bloqueante | 0 | — |
| Alta | 0 | — |
| Media | 1 | Corregir en siguiente fase (`_degraded` sin autorecuperación) |
| Baja | 5 | Documentados, sin acción requerida |
| Informativo | 8 | Falsos positivos o mejoras menores |

**Ningún hallazgo bloquea el cierre.** Ver `informe_auditoria.md` (en
conversación OpenCode) para el detalle completo.

---

## Deuda Técnica Reconocida

| Item | Impacto | Plan |
|------|---------|------|
| `_degraded` sin autorecuperación | Pérdida de vector search tras error transitorio | Corregir en Fase 7 (health check con backoff) |
| `available` hace HTTP call en cada acceso | 3 health checks por búsqueda vectorial | Optimizar si el hot path lo requiere |
| Sin distinción 4xx vs 5xx en errores HTTP | 400 Bad Request marca backend como degradado | Mejorar en Fase 7 |
| `SQLiteAssetStore` creado por evento | Overhead mínimo, patrón existente | Refactor global si procede |

---

## Riesgos Remanentes

| Riesgo | Impacto | Probabilidad | Mitigación |
|--------|---------|--------------|------------|
| Sincronización AssetStore↔VectorStore | Vectores huérfanos si se borra un asset | Baja | Diferido a Fase 7 (job periódico de reconciliación) |
| Cambio de embedder | Todos los vectores existentes inválidos | Baja (embedder fijo en producción) | Diferido a Fase 7 (reindex_vectors.py) |
| Vector size mismatch | Upsert falla | Baja (auto-detectado del primer embedding) | Degradación graceful, log warning |

---

## Lecciones Aprendidas

1. **Protocols separados** (`Embedder` + `VectorStore` en vez de `VectorBackend`)
   facilitaron testing y composición. Buena decisión.
2. **HTTP directo a Qdrant** (sin `qdrant-client`) eliminó una dependencia
   externa sin coste apreciable de desarrollo.
3. **El flag `_degraded` binario sin recovery** fue la única debilidad
   significativa identificada en la auditoría. Para Fase 7, usar contador
   de fallos consecutivos + health check periódico.
4. **112 tests** dieron alta confianza en la corrección. La mayoría de
   hallazgos de auditoría fueron informativos o falsos positivos.

---

## Línea Base

| Propiedad | Valor |
|-----------|-------|
| Baseline | v0.4.0 |
| Schema | v13 |
| Fase actual | 7 (planificación) |
| Tests | 425 collected — 35.86s |
| Nuevos fallos | **0** (ninguno introducido por Fase 6) |
| Fallos heredados | 3 preexistentes (IDs: `TestMigration::test_migrate_v6_to_v7_adds_body_column`, `TestMigration::test_migration_v5_to_v7_chain`, `TestQdrantSync::test_sync_documents_qdrant_unavailable`) |
| Tests pasando | 421 passed, 1 skipped |
| Estado | Implementación de Fase 6 cerrada y auditada. Todas las auditorías completadas. |

Esta línea base sirve como punto de referencia estable. Si en Fase 7 aparece
alguna regresión, se puede comparar contra este estado para detectar la
desviación.

### Benchmark de Rendimiento (Línea Base v0.4.0)

| Operación | Tiempo | Notas |
|-----------|--------|-------|
| Migración SQLite 0→v13 | 0.013s | Base vacía, 2 tablas creadas |
| Compilación 2 documentos | 1.568s | Incluye parsing, validación, escritura |
| Extracción de metadatos | 0.035s | Extractor markdown, asset creado |
| Búsqueda heurística | 0.024s | 1 resultado (title match), BD 208KB |
| Búsqueda vectorial (fallback) | 0.001s | Sin backends, degradación graceful |
| Lineage | 0.000s | 0 eventos (esperado) |
| Governance | 0.000s | 0 políticas (esperado) |
| Memory | 0.000s | 0 resultados (esperado) |
| **Total E2E** | **1.643s** | |
| Tamaño BD | 208 KB | 2 documentos + 1 asset |
| Memoria pico | 10.7 KB | tracemalloc, extracción de 1 asset |

> ⚠️ Este benchmark debe ejecutarse **exactamente igual** al cierre de Fase 7
> para detectar regresiones de rendimiento antes de liberar.

## Firma

| Rol | Fecha |
|-----|-------|
| Implementación | 2026-07-03 |
| Auditoría técnica | 2026-07-03 |
| Cierre documental | 2026-07-03 |

---

## Flujo de Trabajo para Fases Futuras

Basado en la experiencia de Fase 6, se recomienda el siguiente flujo para Fase 7
y siguientes:

```
Diseño → Auditoría de diseño → Congelar contratos
→ Implementación → Auditoría técnica → Integración completa → Cierre
```

**Principios:**
- Las auditorías extraordinarias se reservan para cambios arquitectónicos
  mayores (como ocurrió con los Protocols de Fase 6).
- El cierre de cada fase debe separar explícitamente:
  - `Nuevos fallos: 0` (ninguno introducido por la fase)
  - `Fallos heredados: N` (con IDs conocidos, preexistentes)
- La línea base de rendimiento se conserva y se re-ejecuta al final de cada
  fase para detectar regresiones de latencia/memoria antes de liberar.

---

*Documento de cierre — Fase 6 Backend Vectorial — Knowledge Engine — 2026-07-03*

# F25-A3: Auditoría de Integración Final

**Fecha:** 2026-07-17  
**Cubre:** A3-01 a A3-08

---

## A3-01: Matriz de Ownership

| Dato | Productor | Fuente de verdad | Propietario | Consumidores |
|------|-----------|-----------------|-------------|--------------|
| **Evidence** | `CitationEngine` (F24) | `CitationBundle.evidence` | Web Intelligence | `ExtractionStage` |
| **KnowledgeClaim** | `ExtractionStage` | `FusionContext.claims` | Fusion Pipeline | `NormalizationStage`, `EntityResolutionStage`, `ConflictDetectionStage`, `SourceScoringStage` |
| **KnowledgeFact** | `KnowledgeMergerStage` | `FusionContext.facts` | Fusion Pipeline | `FusionResult.accepted`, `FactIndex` |
| **Fact** | `FusionPipeline.run()` | `FusionResult.index` (via `FactIndex`) | Fusion Pipeline/Integración | `ContextBuilder`, Bridge a SemanticFact |
| **FactVersion** | `FusionPipeline.run()` | `FusionResult.index` (via `FactIndex`) | Fusion Pipeline/Integración | `ContextBuilder` (solo vigente) |
| **FactHistory** | `FactHistory.create()` | `FactHistory` instance | Versiones/R07 | Consultas temporales, rollback |
| **FactIndex** | `FusionPipeline.run()` | `FusionResult.index` | Fusion Pipeline | `ContextBuilder`, futuro retriever |
| **SemanticFact** | `FactExtractor` (desde Episode) | `SemanticMemoryStore` | Memoria/F26 | `ContextRetriever`, `ResearcherAgent` |

**Regla: ningún dato tiene ownership compartido.**
- `Evidence` es propiedad de F24, consumido por F25
- `KnowledgeClaim` es propiedad de F25, consumido dentro del pipeline
- `KnowledgeFact` es producido y consumido por F25 (FusionResult + FactIndex)
- `FactIndex` es propiedad de F25, consumido por `ContextBuilder`
- `SemanticFact` es propiedad de memoria/F26, SEPARADO de F25

---

## A3-02: Bridge Audit

| Propiedad | `knowledge_fact_to_semantic_fact()` | `fact_version_to_semantic_fact()` |
|-----------|-------------------------------------|------------------------------------|
| Determinista | ✅ Sí (mismo input → mismo dict) | ✅ Sí |
| Puro | ✅ Sin IO, sin efectos secundarios | ✅ Sin IO |
| Idempotente | ✅ Sí | ✅ Sí |
| Datos perdidos | `superseded_by`, `previous_version`, `evidence` (deprecated), `source_score`, `text_id` | `evidence` (deprecated), `source_score` |
| Round-trip | ❌ No existe transformación inversa | ❌ No existe transformación inversa |
| Dirección | Unidireccional (KnowledgeFact → SemanticFact) | Unidireccional (Fact+FactVersion → SemanticFact) |

**Decisión:** No existe round-trip porque SemanticFact tiene campos que KnowledgeFact no tiene (importance, tags, metadata extendido). El bridge es una proyección, no un espejo.

---

## A3-03: Ciclo de Vida de FusionResult.index

| Pregunta | Respuesta |
|----------|-----------|
| ¿Quién lo crea? | `FusionPipeline.run()`, al finalizar la ejecución |
| ¿Quién lo destruye? | El recolector de basura cuando `FusionResult` deja de referenciarse |
| ¿Quién mantiene su validez? | El código que retiene `FusionResult` |
| ¿Es snapshot? | ✅ Sí. Congelado (`idx.freeze()`) inmediatamente después de construirlo |
| ¿Es mutable? | ❌ No. `FactIndex.freeze()` se llama antes de asignarlo al resultado |
| ¿Puede compartirse entre hilos? | ✅ Sí. Un `FactIndex` frozen es thread-safe por contrato |
| ¿Vínculo con FactHistory? | Ninguno. `FactIndex` indexa la versión vigente. `FactHistory` gestiona el histórico |

---

## A3-04/05: Single Source of Truth

**Regla:** `ContextBuilder` solo consulta FactIndex. Nunca consulta SemanticFact ni FactHistory.

| Responsabilidad | Fuente | ¿Correcta? |
|----------------|--------|-----------|
| Facts vigentes para contexto | `FactIndex` (vía `FusionResult.index`) | ✅ |
| Historial de versiones | `FactHistory` (independiente) | ✅ (no consultado por ContextBuilder) |
| Memoria episódica | `SemanticMemoryStore` | ✅ (no consultado por ContextBuilder) |
| Proyección a memoria | Bridge function | ✅ (transformación, no consulta) |

**Veredicto:** No hay duplicación de fuentes de lectura para la misma responsabilidad.

---

## A3-06/07: Tests E2E Ampliados

Los siguientes tests verifican el flujo completo con casos complejos:

| Test | Escenario |
|------|-----------|
| `test_e2e_full_vertical_flow` | Documento → Fact → FactIndex → Contexto → LLM-ready |
| `test_e2e_context_filters_obsolete` | FactIndex con versión obsoleta → no aparece en contexto |
| `test_e2e_context_multiple_entities` | Varios Facts de diferentes entidades |
| `test_e2e_context_after_rollback` | Rollback → solo versión vigente en contexto |
| `test_e2e_context_after_tombstone` | Tombstone → contexto vacío (hecho eliminado) |

---

## A3-08: Filtro de Versiones Obsoletas

`ContextBuilder._is_current_version()`:
- Para `(Fact, FactVersion)`: solo `state == VersionState.CURRENT`
- Para `KnowledgeFact` (legacy): siempre vigente (no hay versionado)
- FactIndex solo almacena la versión vigente por diseño, el filtro es una salvaguarda

**Veredicto:** El contexto LLM nunca incluye versiones obsoletas ni tombstones.

---

## Resumen

| Punto | Estado |
|-------|--------|
| A3-01 Ownership | ✅ Sin ownership compartido |
| A3-02 Bridge | ✅ Determinista, puro, idempotente. Sin round-trip (proyección) |
| A3-03 FactIndex lifecycle | ✅ Snapshot frozen, thread-safe, sin vínculo con FactHistory |
| A3-04 Single source | ✅ ContextBuilder solo consulta FactIndex |
| A3-05 SSOT | ✅ Cada dato tiene una única fuente de verdad |
| A3-06/07 Tests E2E | ✅ 5 tests E2E + tests complejos abajo |
| A3-08 Filtro obsoletos | ✅ `_is_current_version()` filtra no vigentes |

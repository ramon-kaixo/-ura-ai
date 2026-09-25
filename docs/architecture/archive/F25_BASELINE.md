# F25 — Baseline Inmutable

**Tag:** `v0.25.0-fase25`  
**Estado:** ✅ CERRADA  
**Congelado desde:** 2026-07-17  

Este documento constituye el baseline inmutable de F25. No se modificará sin un ADR de excepción aprobado.

---

## 1. ADRs Congelados

| ADR | Título | Archivo |
|-----|--------|---------|
| ADR-025-01 | Fusión como capa sobre KE | `docs/architecture/ADR-025-01.md` |
| ADR-025-02 | Knowledge Identity Model | `docs/architecture/ADR-025-02-KNOWLEDGE_IDENTITY.md` |
| ADR-025-03 | Fact Versioning Model | `docs/architecture/ADR-025-03-FACT_VERSIONING.md` |
| ADR-025-04 | Hash & Identity Policy | `docs/architecture/ADR-025-04-HASH_IDENTITY_POLICY.md` |

---

## 2. Métricas Oficiales Congeladas

### Calidad Semántica

| Métrica | Target |
|---------|--------|
| Entity resolution accuracy | >95% |
| Conflict precision | >98% |
| Conflict recall | >95% |
| False merge rate | <1% |
| Duplicate fact rate | <0.5% |

### Rendimiento

| Métrica | Target |
|---------|--------|
| Resolution latency p50 | <50ms |
| Resolution latency p99 | <500ms |
| Fact lookup p50 | <5ms |
| Fact lookup p99 | <50ms |

### Reproducibilidad

| Métrica | Target |
|---------|--------|
| Knowledge Stability | >99.9% |
| Provenance completeness | 100% |
| Provenance coverage | 100% |

### Escalabilidad

| Métrica | Target |
|---------|--------|
| Incremental update cost | O(Δ) |
| Peak RAM por millón de hechos | TBD (medir en F26) |
| Index build time | TBD (medir en F26) |

---

## 3. Benchmarks Oficiales Congelados

| Benchmark | Target | Límite |
|-----------|--------|--------|
| FactIndex build 1K | <100ms | — |
| FactIndex build 10K | <500ms | — |
| FactIndex lookup 10K | <50ms | — |
| FactHistory add 10 | <10ms | — |
| FactHistory add 1K | <100ms | — |
| FactHistory rollback amid 1K | <1ms | — |
| FactHistory version_at (100 queries) | <100ms | — |
| E2E flow (100 evidencias) | <2s pipeline | — |

---

## 4. Presupuesto de Memoria Congelado

| Componente | Bytes/unidad | 1M unidades |
|-----------|-------------|-------------|
| Fact (identidad) | ~120 | ~120 MB |
| FactVersion (contenido) | ~250 | ~250 MB |
| FactHistory (1 history + N versions) | ~200 + N×250 | ~250 MB |
| FactIndex (por fact) | ~200 | ~200 MB |
| KnowledgeFact (legacy) | ~450 | ~450 MB |

**Total estimado 1M Facts × 1 versión:** ~1.2 GB  
**Total estimado 1M Facts × 10 versiones:** ~3.7 GB

---

## 5. Presupuesto Temporal Congelado

| Operación | Volumen | Target |
|-----------|---------|--------|
| `FactHistory.add_version` | 1 | <10µs |
| `FactHistory.add_version` | 100K batch | <5s |
| `FactHistory.rollback` | 100K history | <10ms |
| `FactHistory.to_dict` | 10K versions | <150ms |
| `FactHistory.from_dict` | 10K versions | <150ms |
| `FactIndex.lookup` | 10K facts | <10ms |
| `FactIndex.add_fact` | 10K batch | <100ms |
| Serialize→Deserialize→Rebuild | 10K | <300ms |

---

## 6. Invariantes Congelados

### Identidad

| ID | Invariante |
|----|-----------|
| I01 | `fact_id = SHA-256(normalize(subj), normalize(pred), normalize(obj))[:16]` |
| I02 | `fact_id` es inmutable una vez creado |
| I03 | Dos Facts con el mismo `fact_id` son el mismo hecho |
| I04 | `normalize_identity()` es la única implementación canónica |
| I05 | Cambio en subject/predicate/object → nuevo Fact |
| I06 | Cambio en confidence/evidence/provenance → nueva versión |

### Versionado

| ID | Invariante |
|----|-----------|
| V01 | `FactVersion.fact_id == FactHistory.fact_id` |
| V02 | `FactHistory.current ∈ FactHistory.versions.keys()` |
| V03 | Cadena `current → supersedes → ... → None` sin ciclos |
| V04 | `version_id` independiente del orden de inserción |
| V05 | Rollback NO crea nueva versión |
| V06 | Rollback NO elimina versiones posteriores |
| V07 | DELETE lógico mantiene la versión en FactHistory |
| V08 | DELETE físico elimina Fact + FactHistory en cascada |
| V09 | Toda FactVersion pertenece a un FactHistory |
| V10 | No existen FactVersion sin FactHistory |

### Determinismo

| ID | Invariante |
|----|-----------|
| D01 | Misma entrada + configuración → mismo conjunto de Facts |
| D02 | `created_at` debe pasarse explícitamente |
| D03 | `EntityResolver.resolve()` sin estado mutable externo |
| D04 | `ScoringStrategy.select()` sin estado mutable externo |
| D05 | `make_fact_id()` produce el mismo ID para los mismos parámetros normalizados |

### Provenance

| ID | Invariante |
|----|-----------|
| P01 | `FactVersion.provenance` contiene todos los claim_ids origen |
| P02 | `FusionProvenance` registra todos los componentes |
| P03 | Toda transformación del pipeline deja `StageProvenance` |
| P04 | `StageProvenance.timestamp` reproducible |

### Concurrencia

| ID | Invariante |
|----|-----------|
| C01 | `FactIndex` frozen es thread-safe |
| C02 | `FactIndex` mutable requiere serialización externa |
| C03 | `EntityRegistry` inmutable tras `__init__` |
| C04 | `FusionPipeline.run()` crea `FusionContext` propio |

### Rendimiento

| ID | Invariante |
|----|-----------|
| R01 | `FactIndex.lookup()` O(1) amortizado |
| R02 | `FactIndex.add_fact()` O(1) amortizado |
| R03 | `FactHistory.add_version()` O(1) |
| R04 | `make_fact_id()` < 1µs |

---

## 7. Contratos Públicos Congelados

### Paquete `motor.core.fusion` (38 símbolos)

```
ChangeDetector, Conflict, ConflictGraph, ConflictResolver, ConflictType,
ContextBuilder, EntityResolver, EvidenceSet, Fact, FactIndex, FactTombstone,
FactVersion, FusionConfig, FusionContext, FusionEngine, FusionPipeline,
FusionProvenance, FusionRegistry, FusionResult, FusionStage, KnowledgeClaim,
KnowledgeDelta, KnowledgeFact, KnowledgeMerger, MemoryCandidateSelector,
PipelineStage, ResolutionStatus, ResolvedEntity, SourceScore, SourceScorer,
StageProvenance, VersionState,
fact_version_to_semantic_fact, knowledge_fact_to_semantic_fact,
make_claim_id, make_conflict_id, make_fact_id, make_version_id,
normalize_identity
```

### Paquete `motor.core.fusion.stages` (21 símbolos)

```
BasicChangeDetector, CachePolicy, ConflictDetectionStage,
ContextualEntityResolver, EntityDef, EntityRegistry, EntityResolutionStage,
ExtractionStage, KeywordScorer, KnowledgeDeltaStage, KnowledgeMergerStage,
LRUCache, MemoryCandidateSelectionStage, NaiveConflictResolver,
NormalizationStage, QualitySourceScorer, RuleBasedEntityResolver,
ScoringStrategy, SimpleKnowledgeMerger, SourceScoringStage, ThresholdSelector
```

---

## 8. Prohibiciones

| Prohibición | Justificación |
|-------------|---------------|
| ❌ Modificar `__all__` de `motor.core.fusion` o `stages` | Breaking change en API pública |
| ❌ Cambiar firmas de ABCs en `base.py` | Rompe todas las implementaciones |
| ❌ Eliminar `normalize_identity()` o cambiar su algoritmo | Rompe IDs deterministas |
| ❌ Modificar `make_fact_id()` o `make_version_id()` | Rompe identidad de Facts |
| ❌ Cambiar constantes de benchmarks ya publicadas | Invalida comparaciones históricas |
| ❌ Añadir nuevas capacidades a F25 | Deben ir en F26+ |
| ❌ Modificar ADRs de F25 | Requiere ADR de excepción |

---

*Este baseline se actualiza únicamente si se aprueba un ADR de excepción que demuestre bug crítico, vulnerabilidad o regresión demostrada.*

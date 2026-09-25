# F25 Auditoría de Integración (A1) + Auditoría Global (A2)

**Fecha:** 2026-07-17  
**Alcance:** F18–F25  
**Propósito:** Radiografía arquitectónica completa antes de F26. No propone implementaciones.

---

# HALLAZGOS CRÍTICOS

## C-01: Ciclo Bidireccional core/ ↔ motor/ via config_manager

**Severidad:** Crítica  
**Impacto:** Alto  
**Probabilidad:** Alta  
**Coste de corrección:** Alto (3-5 días)  
**Riesgo futuro:** Importación circular, tests no deterministas, error de importación intermitente

**Evidencia:**
```
core/config_manager.py ←── motor/core/config.py
                         ←── motor/core/llm/__init__.py
                         ←── motor/core/llm/ollama.py
                         ←── motor/cli/cmd_ura.py

core/memory_engine.py ──→ motor.core.config.UraConfig
core/auto_reindex.py  ──→ motor.core.config
core/debate/           ──→ motor.core.llm.generate
core/ura_multi_agent  ──→ motor.core.llm.generate
core/mochila/         ──→ motor.core.secrets, motor.core.state
```

15 archivos en `core/` importan de `motor/`. 4 archivos en `motor/` importan de `core/`. La ruta `motor/core/config.py → core.config_manager.CONFIG` crea un ciclo verdadero: importar `motor` puede desencadenar `core.config_manager` que puede desencadenar módulos que importan `motor` de nuevo.

**Clasificación:** Breaking change inminente. La migración a F26 requerirá resolver este ciclo para evitar errores de importación.

---

## C-02: Dos Sistemas de Hechos Paralelos Sin Puente

**Severidad:** Crítica  
**Impacto:** Muy alto  
**Probabilidad:** Alta  
**Coste de corrección:** Medio (5-8 días)  
**Riesgo futuro:** F25 produce KnowledgeFact. F26 necesita alimentar memoria. Sin puente, F25 es una isla.

**Evidencia:**
```
KnowledgeFact (F25)                     SemanticFact (memoria)
┌──────────────────────────┐            ┌──────────────────────────┐
│ id: str                  │            │ id: str                  │
│ subject: str             │            │ subject: str             │
│ predicate: str           │            │ predicate: str           │
│ object: str              │            │ object_value: str        │
│ confidence: float        │            │ confidence: float        │
│ evidence_ids: tuple      │            │ importance: float        │
│ provenance: tuple        │            │ source_episode_ids: list │
│ version: int             │            │ version: int             │
│ created_at: float        │            │ tags: list[str]          │
│ superseded_by: str | None│            │ metadata: dict           │
└──────────────────────────┘            └──────────────────────────┘
       ↑ NO HAY PUENTE                      ↑
  FusionPipeline                       FactExtractor (desde Episode)

Los dos sistemas operan en paralelo, sobre los mismos dominios, con modelos
casi idénticos, pero no comparten datos ni tipo.
```

**F25 produce Facts que nadie consume.** MemoryCandidateSelectionStage (selector.py) es un placeholder que nunca escribe en `SemanticMemoryStore`. El pipeline termina en `FusionResult` y los Facts quedan en memoria sin persistir.

---

## C-03: Pipeline F25 Termina en el Vacío

**Severidad:** Crítica  
**Impacto:** Alto  
**Probabilidad:** Cierta  
**Coste de corrección:** Bajo (1-2 días)  
**Riesgo futuro:** F25 completo pero no integrado con nada

**Flujo actual:**
```
Evidence → Claim → Entity → Conflict → Fact → FusionResult → (nada)
                                                             └→ Nadie consume
```

`MemoryCandidateSelectionStage._execute()` solo establece `context.statistics["candidates_returned"] = 0`. No escribe en `SemanticMemoryStore`, no indexa en `FactIndex`, no alimenta ningún `ContextRetriever`. El pipeline computa Facts y luego los descarta.

El `FactIndex` existe como componente independiente pero no está integrado en el pipeline (ningún `PipelineStage` lo usa). `FusionResult` no tiene campo para `FactIndex`.

---

## C-04: F25 No Participa en el Camino LLM

**Severidad:** Crítica  
**Impacto:** Muy alto  
**Probabilidad:** Alta  
**Coste de corrección:** Alto (1-2 semanas)  
**Riesgo futuro:** Las respuestas del LLM no usan el conocimiento fusionado

**Flujo LLM actual:**
```
Conversación/Agente → Episode → FactExtractor → SemanticFact → SemanticMemoryStore → ContextRetriever → LLM
                                                                                                      ↑
                                                                                    F25 NO participa ──┘
```

El `ResearcherAgent` (motor/intelligence/agents/researcher.py) usa `ContextRetriever` que consulta `SemanticMemoryStore`, que almacena `SemanticFact` extraídos de `Episode` por `FactExtractor`. Los `KnowledgeFact` de F25 nunca llegan a este camino.

**Dos caminos paralelos e inconexos:**
- F25: `Document → Evidence → Claim → Fact → (nadie consume)`
- Memoria: `Episode → SemanticFact → SemanticMemoryStore → ContextRetriever → LLM`

---

# HALLAZGOS ALTOS

## A-01: FusionContext.bundle: Any (Pendiente desde ALTA-05)

**Severidad:** Alta  
**Impacto:** Medio  
**Probabilidad:** Cierta  
**Coste:** Bajo (< 1h)

`FusionContext.bundle: Any = None` en `models.py:425`. Impide verificación estática, serialización distribuida y documentación de API. Identificado como ALTA-05 en F25-B5, no resuelto.

---

## A-02: 26 Anotaciones Any Sin Resolver

**Severidad:** Alta  
**Impacto:** Medio  
**Probabilidad:** Cierta  
**Coste:** Medio (2-3 días)

Distribución: 7 en `motor/core/fusion/`, 19 en `motor/intelligence/`, 2 en `motor/core/web/`, 3 en `motor/core/web/models.py` (solo to_dict).

Especialmente críticas en:
- `FactIndex._extract_keys(entry: Any)` — deshace el tipado del índice
- `ForgettingPolicy.should_forget(self, record: Any, ...)` — 6 implementaciones con `Any`
- `ResearcherAgent.memory_store: Any = None` — impide verificación del contrato

---

## A-03: 30/55 Paquetes con __init__.py Vacío

**Severidad:** Alta  
**Impacto:** Medio  
**Probabilidad:** Cierta  
**Coste:** Medio (1-2 días)

Sin `__all__` definido, la API pública de cada paquete es implícita. Esto impide:
- Linting de importaciones no utilizadas (F401)
- Documentación automática de API
- Control de breaking changes
- Verificación de exports en CI

Paquetes afectados: `core/memoria/`, `core/seguridad/`, `core/logs/`, `core/inferencia/`, `core/infra/`, `core/cleaner/`, `core/utils/`, `config/`, `knowledge/`, `tests/`, `tests/contracts/`, `knowledge/evaluation/`, `motor/`, `motor/core/`, `motor/cli/`, `motor/guard/`

---

## A-04: Sin Puente KnowledgeFact ↔ SemanticFact

**Severidad:** Alta  
**Impacto:** Alto  
**Probabilidad:** Alta  
**Coste:** Medio (3-5 días)  
**Riesgo futuro:** F25 no puede alimentar memoria

No existe función `knowledge_fact_to_semantic_fact(kf: KnowledgeFact) → SemanticFact` ni `semantic_fact_to_knowledge_fact(sf: SemanticFact) → KnowledgeFact`. Mapeo de campos:

```
KnowledgeFact         → SemanticFact
subject                → subject
predicate              → predicate
object                 → object_value
confidence             → confidence
evidence_ids           → source_episode_ids (semántica diferente)
(no tiene)             → importance (debe calcularse)
(no tiene)             → tags
(no tiene)             → metadata
provenance             → (no tiene equivalente directo)
evidence (Evidence[])  → (no tiene equivalente)
```

---

## A-05: FusionConfig No se Usa en Implementaciones

**Severidad:** Alta  
**Impacto:** Medio  
**Probabilidad:** Cierta  
**Coste:** Bajo (2-4h)

`FusionConfig` define `authority_weight: 0.4, freshness_weight: 0.3, relevance_weight: 0.3`. `QualitySourceScorer` usa pesos hardcodeados (0.5, 0.5) y no lee de `FusionConfig`. Ninguna implementación concreta recibe `FusionConfig` en su constructor.

---

## A-06: EvidenceSet Mutable (list[KnowledgeClaim] Compartido)

**Severidad:** Alta  
**Impacto:** Medio  
**Probabilidad:** Media  
**Coste:** Bajo (< 1h)

`EvidenceSet.claims: list[KnowledgeClaim]` es una lista mutable compartida. Si un `SourceScorer` modifica la lista mientras otro la recorre, hay race condition. Evidencias paralelas pueden corromperse.

Identificado como MEDIA-19 pero sin resolver.

---

## A-07: Statistics Como dict[str, Any] Sin Control

**Severidad:** Alta  
**Impacto:** Medio  
**Probabilidad:** Cierta  
**Coste:** Medio (2-3 días)

`FusionContext.statistics: dict[str, Any]` y `FusionResult.statistics: dict[str, Any]`. Sin esquema definido, cualquier etapa puede escribir cualquier clave. Los keys usados actualmente:

```
claims_extracted, claims_normalized, entities_resolved, entities_ambiguous,
entities_unknown, ambiguous_entity_ids, conflicts_detected, conflicts_unresolved,
claims_scored, facts_merged, claims_with_ambiguous_entities,
deltas_added, deltas_updated, deltas_removed, has_changes,
candidates_requested, candidates_returned, resolver_cache_size,
resolver_cache_maxsize, existing_facts (hack: lista de Facts en statistics)
```

Sin validación, tipado ni documentación.

---

## A-08: Registro de Entidades Sin Versionado

**Severidad:** Alta  
**Impacto:** Bajo  
**Probabilidad:** Media  
**Coste:** Bajo (< 1h)

`EntityRegistry` no tiene `registry_version` ni `dataset_checksum`. No es posible saber si el registro cambió entre ejecuciones. Identificado como ALTA-09 en F25-B5, no resuelto.

---

# HALLAZGOS MEDIOS

## M-01: 10+ Registros con Patrón idéntico Sin Abstracción Compartida

**Severidad:** Media  
**Impacto:** Bajo  
**Probabilidad:** Cierta  
**Coste:** Medio (3-5 días)

`FusionRegistry`, `Registry` (web), `PluginRegistry`, `PluginRegistryV2`, `ProviderRegistry`, `AgentWeightRegistry`, `HealthRegistry`, `MetricsRegistry`, `ReadinessRegistry` — todos siguen el patrón `dict[str, T]` con `register()`/`get()`/`list()`. No heredan de una base común `Registry[T]`. Esto significa:
- 10 implementaciones de `get()` con `raise KeyError`
- 10 implementaciones de `list()` con `list(dict)`
- Sin contrato unificado de concurrencia
- Sin contrato unificado de serialización

---

## M-02: FactIndex Sin Integración en el Pipeline

**Severidad:** Media  
**Impacto:** Alto  
**Probabilidad:** Alta  
**Coste:** Bajo (1-2 días)

`FactIndex` existe como componente independiente (190 tests, benchmarks, concurrencia) pero ningún `PipelineStage` lo usa. `FusionPipeline.run()` no tiene parámetro para recibir un `FactIndex`. `FusionResult` no tiene campo para devolverlo.

El componente más robusto de F25 (FactIndex) no está conectado al pipeline.

---

## M-03: VersionState.TOMBSTONE con Valor "obsolete"

**Severidad:** Media  
**Impacto:** Bajo  
**Probabilidad:** Cierta  
**Coste:** Mínimo (< 1h)

`VersionState.TOMBSTONE = "obsolete"`. El nombre del enum miembro no coincide con su valor. "obsolete" y "tombstone" tienen semántica diferente (un hecho obsoleto puede haber sido reemplazado; un tombstone es una marca explícita de eliminación).

---

## M-04: make_fact_id() Legacy Sigue Acceptando version

**Severidad:** Media  
**Impacto:** Bajo  
**Probabilidad:** Baja  
**Coste:** Bajo (< 1h)

`make_fact_id(subject, predicate, obj, version=1)` mantiene el parámetro `version` por compatibilidad, pero ADR-025-04 establece que `version` NO participa en la identidad. El parámetro existe pero no se usa en el hash. Puede confundir a los consumidores.

---

## M-05: knowledge/engine/ Denso pero Dependiente de motor.core

**Severidad:** Media  
**Impacto:** Medio  
**Probabilidad:** Media  
**Coste:** Alto (1-2 semanas)

`knowledge/engine/` tiene 55+ archivos con dependencias densas internas y 5 dependencias externas de `motor.core` (config, llm, qdrant_client, secrets, state). Cualquier cambio en `motor.core.qdrant_client` afecta a 3 consumidores: `core/memoria/qdrant_store.py`, `knowledge/engine/qdrant_sync.py`, `motor/intelligence/retrieval/vector.py`.

---

## M-06: Módulo agents/ Aislado Pero No Integrado

**Severidad:** Media  
**Impacto:** Medio  
**Probabilidad:** Baja  
**Coste:** Variable

`agents/` (sandbox) está perfectamente aislado con 0 importaciones externas. Esto es bueno para seguridad pero malo para integración: los agentes sandbox no pueden consumir Facts, memoria, ni LLM sin agregar dependencias.

---

## M-07: Pruebas de Concurrencia con Lock Manual

**Severidad:** Media  
**Impacto:** Bajo  
**Probabilidad:** Cierta  
**Coste:** Bajo (1-2 días)

Los tests `test_concurrent_readers_during_add` y `test_concurrent_rollback_during_reads` usan `threading.Lock` manual para proteger las operaciones de FactHistory. La necesidad de lock externo sugiere que FactHistory no es thread-safe por diseño. El contrato de concurrencia documentado (IMP-01 a IMP-15) dice que las escrituras deben serializarse, pero los lectores tendrían race condition sin lock.

---

## M-08: FactHistory.version_at() O(n) en el Peor Caso

**Severidad:** Media  
**Impacto:** Medio  
**Probabilidad:** Alta  
**Coste:** Bajo (< 1 día)

`version_at(timestamp)` recorre la cadena `supersedes` desde `current` hacia atrás. Para consultas en timestamp = 0 con 100K versiones, recorre 100K pasos. El benchmark confirma que 100 consultas en el peor caso toman 2.3s. La complejidad O(k) está documentada pero no hay optimización (binary search on timeline, o índice temporal).

---

## M-09: FusionPipeline.run() No Es Reentrante

**Severidad:** Media  
**Impacto:** Bajo  
**Probabilidad:** Baja  
**Coste:** Documentación (< 1h)

`FusionPipeline.run()` muta `self._stages` (solo lectura, OK) pero no crea nuevo estado por invocación. Sin embargo, si las etapas tienen estado interno mutable (LRUCache, contadores), dos llamadas concurrentes a `run()` pueden interferir. El contrato no está documentado.

---

# HALLAZGOS BAJOS

## B-01: Pre-Existing RUF012 Lint Errors (2)

**Severidad:** Baja
**Ubicación:** `entity_resolver.py:411` (_LEGACY), `source_scorer.py:31` (_TLD_WEIGHTS)

## B-02: Import Ordering en Varios Archivos

**Severidad:** Baja  
**Causa:** `ruff check --fix` ha resuelto la mayoría, pero algunos archivos (`entity_resolver.py`, `__init__.py`) tienen imports no normalizados.

## B-03: tests/test_f25_b2_stages.py Usa RuleBasedEntityResolver Hardcodeado

**Severidad:** Baja  
**Detalle:** El test `test_rule_based_entity_resolver_known` prueba la implementación legacy, no la actual. Si `RuleBasedEntityResolver` se elimina en el futuro, el test fallará.

## B-04: memory_engine.py en core/ Según AGENTS.md Debería Estar en motor/

**Severidad:** Baja  
**Detalle:** `core/memory_engine.py` importa `motor.core.config`, `motor.core.llm`, `motor.core.qdrant_client`. Su ubicación en `core/` es inconsistente con la regla ADR-007 de que `core/` es dominio, no infraestructura.

## B-05: Nomenclatura Inconsistente: "Fusion" vs "Knowledge Fusion"

**Severidad:** Baja  
**Detalle:** El módulo se llama `motor.core.fusion` pero los documentos lo refieren como "Knowledge Fusion". Algunas clases usan prefijo `Fusion` (FusionPipeline, FusionResult), otras `Knowledge` (KnowledgeFact, KnowledgeMerger). Sin convención unificada.

---

# DOCUMENTOS DE SOPORTE (generados durante la auditoría)

| Documento | Contenido |
|-----------|-----------|
| Architecture Dependency Map | Ver task 1: grafo completo con ~120 aristas entre paquetes |
| Domain Model Map | Ver task 2: flujo Document→Evidence→Claim→Entity→Conflict→Fact→FusionResult |
| Ownership Matrix | core/: dominio + infraestructura; motor/: framework + pipelines + memoria + agentes |
| Public API Inventory | 31 símbolos en fusion/, 37 en web/, 40+ en memory/, 27 en agents/ |
| Internal Contract Inventory | 8 ABCs en fusion/, 4 en memory/, 2 en agents/ |
| Mutable State Inventory | 24 entradas (module-level + class-level) |
| Determinism Audit | OK en fusion/ (IDs SHA-256, PipelineStage.deterministic); en riesgo en memory/ (LLMFactExtractor usa LLM) |
| Concurrency Audit | 4 singletons sin lock, 8 registries sin lock, FactHistory requiere lock externo |
| Technical Debt Register | 23 entradas (desde RUF012 hasta Any sin resolver) |
| Risk Register | 8 riesgos activos (ciclo core↔motor, dos sistemas de hechos, sin puente F25→memoria) |

---

# RESUMEN POR SEVERIDAD

| Severidad | Total | Acción recomendada |
|-----------|-------|-------------------|
| 🔴 Crítico | 4 | Resolver antes de F26: ciclo core↔motor, dos sistemas de hechos, pipeline termina en vacío, F25 no participa en LLM |
| 🟠 Alto | 8 | Resolver durante F26: Any, __init__.py vacíos, puente KnowledgeFact↔SemanticFact, FusionConfig, EvidenceSet, statistics, EntityRegistry version |
| 🟡 Medio | 9 | Planificar durante F26: registros sin abstracción, FactIndex no integrado, VersionState, version legacy, knowledge/engine/ dependencies, agents/ aislado, concurrencia, version_at O(n), reentrancia |
| 🟢 Bajo | 5 | Corrección continua: lint, imports, tests legacy, ubicación memory_engine.py, nomenclatura |

---

**Veredicto:** F25 tiene una arquitectura sólida a nivel de componentes individuales (FactIndex: 190 tests, concurrencia, benchmarks) pero carece de integración vertical con el resto del sistema. Los 4 hallazgos críticos comparten un mismo patrón: **cada componente existe, pero no están conectados**. F26 debería priorizar la integración sobre nuevas capacidades.

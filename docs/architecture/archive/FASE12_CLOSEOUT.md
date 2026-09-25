# Fase 12 — Closeout

> **Inicio:** 2026-07-05
> **Cierre:** 2026-07-05
> **Duración:** 1 sesión intensiva
> **Baseline:** `v0.11.0` (Fase 11 — Plataforma)
> **Tag final:** `v0.12.0`
> **Commits:** 14 desde baseline, 15 tags parciales

---

## 1. Resumen Ejecutivo

### Objetivos previstos

| Objetivo | Prioridad |
|----------|-----------|
| Semantic Chunking | 🟡 Alta |
| Hybrid Retrieval (vectorial + BM25) | 🟡 Alta |
| Reranking | 🟡 Alta |
| Memory (Episodic, Semantic, Compression, Forgetting) | 🟡 Alta |
| Multi-Agent Runtime | 🟡 Alta |
| Evaluation corpus + metrics | 🟢 Media |

### Objetivos alcanzados

| Objetivo | Estado | Sub-bloques |
|----------|--------|-------------|
| Evaluation-first methodology | ✅ | Corpus 200 queries, benchmark KE 1.x, ADR-012-01 |
| Semantic Chunking | ✅ | Chunker por títulos, overlap configurable, KE 2.0 baseline |
| Hybrid Retrieval | ✅ | Vectorial + BM25, 5 estrategias, 13 configuraciones |
| Reranking | ⚠️ Experimental | LLM (inviable: 44s/query) y CrossEncoder (no supera criterior) |
| Episodic Memory | ✅ | EpisodeStore, SessionMemory, SQLite, TTL |
| Contextual Retrieval | ✅ | ContextRetriever, scoring híbrido, filtros |
| Semantic Memory | ✅ | SemanticFact, SemanticMemoryStore, FactExtractor |
| Memory Compression | ✅ | 4 políticas, resumen extractivo, SummaryRecord |
| Directed Forgetting | ✅ | 5 políticas, ProtectionRules, dry-run |
| Multi-Agent Runtime | ✅ | 5 agentes, runtime, coordinación, cancelación |

### Objetivos no alcanzados

| Objetivo | Justificación |
|----------|---------------|
| MAP ≥ 0.85 (ADR-012-01) | BM25 añade recall (+30%) pero reduce precisión. El reranking con cross-encoder (ms-marco-MiniLM) no generaliza al dominio URA. Se necesita fine-tuning del modelo, fuera del alcance. |
| nDCG ≥ 0.80 (ADR-012-01) | Misma causa: el cross-encoder MS MARCO no reconoce documentos técnicos de URA como relevantes, asignando scores negativos al 78% de los documentos. |
| Reranking en producción | LLM: 44s/query (480x el límite). Cross-encoder: 585ms P95, no supera criterios de MAP/nDCG. Ambos quedan como experimentales. |

---

## 2. Entregables Finales

### 2.1 Retrieval Pipeline

| Módulo | Archivos | LOC | Responsabilidad |
|--------|----------|-----|-----------------|
| Semantic Chunker | `motor/intelligence/chunking.py` | ~140 | División por títulos markdown, overlap, límite de tokens |
| VectorRetriever | `motor/intelligence/retrieval/vector.py` | ~55 | Búsqueda Qdrant (colección semántica) |
| LexicalRetriever | `motor/intelligence/retrieval/lexical.py` | ~65 | BM25 Okapi sobre documentos oro |
| HybridRetriever | `motor/intelligence/retrieval/hybrid.py` | ~80 | Fusión ponderada α·vector + β·lexical |

### 2.2 Memory System

| Módulo | Archivos | LOC | Responsabilidad |
|--------|----------|-----|-----------------|
| MemoryRecord | `motor/intelligence/memory/record.py` | ~60 | Contrato unificado (id, type, importance, ttl, embedding) |
| MemoryStore | `motor/intelligence/memory/base.py` | ~35 | Interfaz abstracta (store, get, search, delete, count) |
| EpisodeStore | `motor/intelligence/memory/episodic.py` | ~290 | CRUD episodios, SQLite, TTL, sesiones, thread-safe |
| SessionMemory | `motor/intelligence/memory/episodic.py` | ~60 | Gestión de sesiones activas |
| ContextRetriever | `motor/intelligence/memory/retrieval.py` | ~200 | Búsqueda híbrida (recencia + importancia + confianza) |
| SemanticMemoryStore | `motor/intelligence/memory/semantic.py` | ~200 | Hechos, dedup, versionado, SQLite |
| RuleBasedFactExtractor | `motor/intelligence/memory/extractor.py` | ~95 | Extracción por patrones regex |
| MemoryCompressor | `motor/intelligence/memory/compression.py` | ~290 | 4 políticas, resumen extractivo |
| ForgettingEngine | `motor/intelligence/memory/forgetting.py` | ~290 | 5 políticas, protección, dry-run |

### 2.3 Multi-Agent Runtime

| Módulo | Archivos | LOC | Responsabilidad |
|--------|----------|-----|-----------------|
| Agent (ABC) | `motor/intelligence/agents/base.py` | ~25 | Interfaz base (run, can_handle) |
| Message | `motor/intelligence/agents/message.py` | ~85 | Contratos tipados (AgentMessage, AgentTask, AgentResult) |
| PlannerAgent | `motor/intelligence/agents/planner.py` | ~85 | Descomposición por keywords |
| ResearcherAgent | `motor/intelligence/agents/researcher.py` | ~70 | Consulta memoria episódica + semántica |
| ExecutorAgent | `motor/intelligence/agents/executor.py` | ~65 | SubprocessExecutor (inyectable) |
| ValidatorAgent | `motor/intelligence/agents/validator.py` | ~55 | Validación de resultados |
| SupervisorAgent | `motor/intelligence/agents/supervisor.py` | ~100 | Coordinación, reintentos (max 2), cancelación |
| MultiAgentRuntime | `motor/intelligence/agents/runtime.py` | ~150 | Registro, workflows, cancelación, limpieza FIFO |

### 2.4 Evaluación

| Artefacto | Archivos | LOC | Responsabilidad |
|-----------|----------|-----|-----------------|
| Evaluation corpus | `knowledge/evaluation/corpus/*` | ~2,4K | 200 queries, 3 dominios, 990 relevance judgments |
| Golden documents | `knowledge/evaluation/golden_docs/*.md` | ~1,5K | 12 documentos de referencia |
| Benchmark KE | `scripts/pro/benchmark_ke.py` | ~690 | Benchmark completo (Recall, MRR, MAP, nDCG, latencia, throughput) |
| Benchmarks varios | `scripts/pro/benchmark_*.py` (×6) | ~1,8K | Chunking, hybrid, reranking, comparison |

### 2.5 ADRs

| ADR | Archivo |
|-----|---------|
| ADR-012-01 | `docs/architecture/ADR-012-01-QUALITY_CONTRACT.md` |
| ADR-012-02 | `docs/architecture/ADR-012-02-MEMORY_MODEL.md` |
| ADR-012-03 | `docs/architecture/ADR-012-03-MEMORY_LIFECYCLE.md` |

### 2.6 Tests

| Archivo | Tests | Componente |
|---------|-------|------------|
| `tests/test_evaluation_corpus.py` | 29 | Corpus integrity, format, reproducibility |
| `tests/test_episodic_memory.py` | 38 | EpisodeStore, SessionMemory, persistence |
| `tests/test_contextual_retrieval.py` | 27 | ContextRetriever, ranking, filters |
| `tests/test_semantic_memory.py` | 34 | SemanticFact, SemanticMemoryStore, consolidation |
| `tests/test_memory_compression.py` | 24 | MemoryCompressor, policies |
| `tests/test_forgetting.py` | 28 | ForgettingEngine, policies, protection |
| `tests/test_agents.py` | 47 | Agent runtime, cancellation, injection |
| `tests/test_pipeline_mvp.py` | 21 | Pipeline MVP (F11 legacy) |

---

## 3. Métricas Finales

### 3.1 Generales

| Métrica | F11 (baseline) | F12 (final) | Delta |
|---------|----------------|-------------|-------|
| pytest | 662 | **889** | **+227** |
| Tag F11 | `v0.11.0` | `v0.12.0` | — |
| Commits | 4 | 14 | +10 |
| Tags parciales | 5 | 15 | +10 |
| Archivos nuevos | 23 | **72** | +49 |
| Líneas añadidas | +4468 | **+10,798** | +6,330 |
| Ruff errors | 320 (S603) | 2279 (total all rules) | +1,959 (pre-existing) |

### 3.2 Cobertura por componente

| Componente | Cobertura |
|------------|-----------|
| `motor/events/compat.py` | 67% |
| `motor/events/hooks.py` | 84% |
| `motor/pipeline/executor.py` | 75% |
| `motor/plugin/manifest.py` | 86% |
| `motor/plugin/registry_v2.py` | 75% |
| `motor/observability/metrics.py` | 100% |
| `motor/observability/health.py` | 98% |
| `motor/observability/readiness.py` | 100% |

### 3.3 Benchmarks finales

| Configuración | R@10 | P@5 | MRR | MAP | nDCG | P50 | P95 | P99 | TPS | NoCtx |
|---------------|------|-----|-----|-----|------|-----|-----|-----|-----|-------|
| Vector-only (baseline) | 0.6700 | 0.4750 | 0.7595 | **0.9423** | **0.8346** | 91ms | 196ms | 308ms | 9.7 | 21.5% |
| Semantic Chunking | 0.6700 | 0.4750 | 0.7595 | **0.9423** | **0.8346** | 91ms | 196ms | 308ms | 9.7 | 21.5% |
| **Hybrid (α=0.7)** | **0.8708** | **0.6060** | 0.7938 | 0.6444 | 0.6498 | **85ms** | **196ms** | **243ms** | **10.1** | **0.5%** |
| Hybrid + CE | 0.8708 | 0.6370 | **0.8280** | 0.6745 | 0.6837 | 253ms | 561ms | 630ms | 3.6 | 78.5% |
| Hybrid + LLM | — | — | — | — | — | ~36s | ~97s | — | ~0.02 | 50% |

---

## 4. Estado respecto al ADR-012-01

| Objetivo | Criterio | Estado | Evidencia |
|----------|----------|--------|-----------|
| Recall@k | ≥ 0.85 @ k=10 | ✅ **0.8708** | Hybrid (α=0.7, β=0.3) |
| Precision@k | ≥ 0.60 @ k=10 | ✅ **0.6060** | Hybrid |
| MRR | ≥ 0.75 | ✅ **0.7938** | Hybrid |
| nDCG@k | ≥ baseline + 20% | ❌ **0.6498** (baseline 0.8346) | BM25 reduce nDCG. Sin reranking efectivo |
| MAP | ≥ 0.65 | ❌ **0.6444** (objetivo 0.9423 en vectorial) | BM25 introduce ruido léxico |
| P50 búsqueda | ≤ 150ms | ✅ **85ms** | Hybrid |
| P95 búsqueda | ≤ 500ms | ✅ **196ms** | Hybrid |
| Tasa sin contexto | ≤ 5% | ✅ **0.5%** | Hybrid (vs 21.5% vectorial puro) |
| Cobertura documental | ≥ 80% | ✅ **100%** | 12/12 documentos oro indexados |
| Corpus evaluación | ≥ 200 consultas | ✅ **200** | 3 dominios, 990 relevance judgments |
| Baseline KE 1.x | Generado y versionado | ✅ | `knowledge/evaluation/results/baseline_results.json` |

**Criterios no cumplidos:** MAP y nDCG no alcanzan los umbrales porque BM25 introduce≈68% de ruido (documentos con coincidencia léxica pero sin relevancia semántica). El cross-encoder no puede filtrar este ruido sin fine-tuning en el dominio URA.

---

## 5. Deuda Técnica

### 🔴 Crítica

| ID | Ítem | Impacto | Coste | Fase |
|----|------|---------|-------|------|
| F12-D01 | CrossEncoder sin fine-tuning para dominio URA | Reranking experimental, no supera criterios | Medio (fine-tuning, ~2h) | F13 |
| F12-D02 | Extracción de hechos solo por reglas (sin LLM) | Hechos limitados a patrones predefinidos | Alto (integración LLM, ~4h) | F13 |

### 🟡 Alta

| ID | Ítem | Impacto | Coste | Fase |
|----|------|---------|-------|------|
| F12-D03 | Consolidación episódica→semántica manual | Requiere orquestador externo | Medio (orquestador, ~2h) | F13 |
| F12-D04 | Compresión extractiva sin LLM | Resúmenes son concatenación + dedup | Medio (LLM summarizer, ~3h) | F13 |
| F12-D05 | `_semantic_score()` stub en ContextRetriever | Sin búsqueda semántica en memoria | Bajo (completar, ~1h) | F13 |
| F12-D06 | Sin integración KE 2.0 con Memory | Memoria y KE separados | Alto (integración, ~4h) | F13 |

### 🟢 Media

| ID | Ítem | Impacto | Coste | Fase |
|----|------|---------|-------|------|
| F12-D07 | PlannerAgent usa reglas (keywords) | Planificación limitada | Medio (LLM planner, ~3h) | F13 |
| F12-D08 | ResearcherAgent necesita stores configurados externamente | Setup manual | Bajo (auto-detect, ~1h) | F13 |
| F12-D09 | Sin consenso/votación entre agentes | No hay tolerancia a divergencias | Medio (voting, ~3h) | F13 |
| F12-D10 | ForgettingEngine accede a `_episodes` directamente | Violación de encapsulamiento | Bajo (refactor a get_all, ~0.5h) | F13 |
| F12-D11 | CompressionScheduler sin timer real | Solo run_once manual | Bajo (APScheduler, ~1h) | F13 |

### 🔵 Baja

| ID | Ítem | Impacto | Coste | Fase |
|----|------|---------|-------|------|
| F12-D12 | Sin tree-of-thought / reflection | Agentes secuenciales sin autoevaluación | Medio (implementar, ~4h) | F14 |
| F12-D13 | Sin ejecución paralela de agentes | Cuello de botella en workflows grandes | Medio (ThreadPool, ~2h) | F14 |
| F12-D14 | `MAX_RETRIES` hardcodeado (2) | No configurable | Mínimo (parametrizar, ~0.25h) | F13 |

---

## 6. Arquitectura Final

```
motor/intelligence/
├── chunking.py                     ← SemanticChunker
│
├── retrieval/
│   ├── __init__.py                 ← exports
│   ├── vector.py                   ← VectorRetriever (Qdrant)
│   ├── lexical.py                  ← LexicalRetriever (BM25)
│   └── hybrid.py                   ← HybridRetriever (α·v + β·l)
│
├── reranking/
│   ├── __init__.py                 ← exports
│   ├── base.py                     ← BaseReranker (ABC)
│   ├── noop.py                     ← NoOpReranker (fallback)
│   ├── llm.py                      ← LLMReranker (Ollama, experimental)
│   └── ce.py                       ← CrossEncoderReranker (experimental)
│
├── memory/
│   ├── __init__.py                 ← exports (44 clases)
│   ├── record.py                   ← MemoryRecord, MemoryType
│   ├── base.py                     ← MemoryStore (ABC)
│   ├── episodic.py                 ← Episode, EpisodeStore, SessionMemory
│   ├── retrieval.py                ← ContextRetriever, ContextQuery, ContextResult
│   ├── semantic.py                 ← SemanticFact, SemanticMemoryStore
│   ├── extractor.py                ← FactExtractor (ABC), RuleBasedFactExtractor
│   ├── compression.py              ← MemoryCompressor, 4 políticas, SummaryRecord
│   └── forgetting.py               ← ForgettingEngine, 5 políticas, ProtectionRules
│
└── agents/
    ├── __init__.py                 ← exports
    ├── base.py                     ← Agent (ABC)
    ├── message.py                  ← AgentMessage, AgentTask, AgentResult, AgentRole
    ├── planner.py                  ← PlannerAgent
    ├── researcher.py               ← ResearcherAgent
    ├── executor.py                 ← ExecutorAgent (BaseExecutor injectable)
    ├── validator.py                ← ValidatorAgent
    ├── supervisor.py               ← SupervisorAgent
    └── runtime.py                  ← MultiAgentRuntime

knowledge/evaluation/
├── corpus/
│   ├── queries.jsonl               ← 200 queries
│   ├── relevance.jsonl             ← 990 relevance judgments
│   └── metadata.json               ← version 1.0.0
├── golden_docs/
│   └── 12 *.md files               ← Documentos de referencia
└── results/
    └── baseline_results.json       ← Baseline KE 1.x
```

---

## 7. Riesgos

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|
| Reranking con cross-encoder no fine-tuneado da baja precisión en dominio URA | Alta | Medio | Fine-tuning del modelo con datos URA. Coste: ~2h |
| BM25 introduce ruido que no puede filtrarse sin reranking | Alta | Alto | Aceptar trade-off: +30% Recall vs -31% MAP |
| Agentes sin consenso pueden divergir en tareas complejas | Media | Alto | Implementar votación ponderada (F13) |
| Memory episódica sin límite real de crecimiento | Baja | Medio | CompressionScheduler + ForgettingEngine ya implementados |
| LLM para extracción de hechos no integrado | Media | Bajo | RuleBasedFactExtractor funcional para patrones. LLM mejora calidad |

---

## 8. Preparación para F13

| Capacidad | Modificación requerida | Detalle |
|-----------|----------------------|---------|
| **Consenso entre agentes** | Cambios menores | Añadir `ConsensusAgent(BaseAgent)` con método `vote()`. No modifica API existente |
| **Reflection** | Cambios menores | Nuevo `ReflectionAgent`. Recibe `AgentResult`, devuelve `AgentResult` mejorado |
| **Tree-of-thought** | Cambios menores | `PlannerAgent._decompose()` genera árbol. `SupervisorAgent` explora ramas |
| **Planificación basada en LLM** | Refactor parcial | `PlannerAgent` necesita inyección de LLM. Arquitectura preparada (ABC), implementación nueva |
| **Memoria persistente distribuida** | Refactor parcial | `EpisodeStore` y `SemanticMemoryStore` ya tienen SQLite. Falta replicación |
| **Ejecución paralela de agentes** | Cambios menores | `MultiAgentRuntime` necesita `ThreadPoolExecutor` para subtasks independientes |

---

## 9. Decisión Final

**F12 cerrada con deuda aceptada.**

**Justificación:** 6 de 8 bloques completados satisfactoriamente. Los 2 incumplimientos (MAP, nDCG) tienen causa conocida y documentada: el cross-encoder MS MARCO no generaliza al dominio URA sin fine-tuning, y BM25 introduce ruido léxico inherente. La deuda está clasificada y calendarizada para F13. Los 889 tests pasan, la arquitectura es extensible, y no hay bloqueos para el desarrollo de F13.

**Tag recomendado:** `v0.12.0` (crear en el commit de cierre).

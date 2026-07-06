# Fase 12 — Progreso

> **Inicio:** 2026-07-05
> **Baseline:** `v0.11.0` (Fase 11)
> **Estado:** En ejecución

---

## Objetivos de la Fase

| ID | Objetivo | Prioridad | Estado |
|----|----------|-----------|--------|
| 12.0 | Contrato de calidad (ADR-012-01, corpus, baseline) | 🔴 Crítica | ✅ Completado |
| 12.1 | KE Core: chunking semántico, retrieval híbrido, reranking | 🟡 Alta | ⏳ Pendiente |
| 12.2 | Context Memory: episódica, semántica, compresión, olvido | 🟡 Alta | 🔮 Planificado |
| 12.3 | Multi-Agent: consenso, Planner, Researcher, Executor, Validator, Supervisor | 🟢 Media | 🔮 Planificado |

---

## Checklist de Cierre

| # | Criterio | Estado |
|---|----------|--------|
| C.1 | KE 2.0 funcional (ranking, chunking, reranking) | ⏳ Pendiente |
| C.2 | Memoria contextual operativa | ⏳ Pendiente |
| C.3 | Multiagente funcional | ⏳ Pendiente |
| C.4 | Sin regresiones funcionales | ⏳ Pendiente |
| C.5 | Benchmark sin degradación (+-10%) | ⏳ Pendiente |
| C.6 | Acta de cierre + tag + baseline + docs | ⏳ Pendiente |

---

## Bitácora

### 2026-07-05 — Bloque 0: Contrato de Calidad (completado)

**ADR-012-01** define métricas (Recall@k, Precision@k, MRR, nDCG, MAP, latencias, cobertura) y corpus de evaluación mínimo (200 consultas, 3 dominios).

**Corpus de evaluación:** `knowledge/evaluation/corpus/` — 200 queries, 990 relevance judgments, 12 documentos únicos.

| Dominio | Consultas | % |
|---------|-----------|---|
| system | 70 | 35.0% |
| code | 65 | 32.5% |
| knowledge | 65 | 32.5% |

**Benchmark KE 1.x:** `scripts/pro/benchmark_ke.py` — usa QdrantClient real con embeddings nomic-embed-text.

**Métricas baseline reales (KE 1.x contra Qdrant + nomic-embed-text):**

| Métrica | Valor | Nota |
|---------|-------|------|
| Recall@10 | **0.0000** | Los documentos gold del corpus no existen en el índice KE actual |
| MRR | **0.0000** | Ídem |
| nDCG@10 | **0.0000** | Ídem |
| Latencia P50 | **102.5ms** | Incluye generación de embedding + búsqueda Qdrant |
| Latencia P95 | **179.1ms** | |
| Latencia P99 | **268.3ms** | |
| Throughput | **8.75 qps** | Limitado por generación de embeddings (Ollama) |
| No-context rate | **50.50%** | Mitad de queries sin resultado con score > 0.6 |
| Doc coverage | **0.00%** | KE index contiene 191 puntos de documentos distintos al corpus de evaluación |

**Limitaciones documentadas:**
- El corpus de evaluación referencia documentos lógicos (p.ej. `eventbus_api_docs`) que no existen como puntos en el índice Qdrant actual.
- KE 1.x tiene 191 vectores indexados de documentos como `doc.md`, `MANIFIESTO_DETERMINISMO.md`, etc. — contenido real del repositorio.
- El baseline es honesto: KE 1.x no puede responder las consultas del corpus porque los documentos de referencia no están indexados.
- La latencia P95 de 179ms es el valor real de KE 1.x (embedding + Qdrant).

**Implicación para KE 2.0:** Las mejoras en chunking, retrieval híbrido y reranking serán absolutas (de 0 a métrica positiva) cuando los documentos correspondientes se indexen correctamente. El baseline sirve como punto de partida, no como techo.

**Tests:** 29 tests para integridad del corpus, formato JSONL, reproducibilidad del benchmark.

**Validación:** ✅ py_compile, ruff (scripts/pro + tests), pytest 691 passed.

**Archivos creados/modificados:**
- `knowledge/evaluation/corpus/queries.jsonl` — 200 queries, 3 dominios
- `knowledge/evaluation/corpus/relevance.jsonl` — 990 relevance judgments
- `knowledge/evaluation/corpus/metadata.json` — metadatos versionados
- `scripts/pro/benchmark_ke.py` — benchmark con soporte QdrantClient real
- `docs/architecture/FASE12_BASELINE.md` — baseline real de KE 1.x
- `knowledge/evaluation/results/baseline_results.json` — resultados reales
- `tests/test_evaluation_corpus.py` — 29 tests
- `docs/architecture/ADR-012-01-QUALITY_CONTRACT.md` (creado previamente)

### 2026-07-05 — Bloque 1a: Semantic Chunking ✅ Aprobado

**Implementado:** `motor/intelligence/chunking.py` — SemanticChunker con split por títulos, solapamiento configurable, límites por tokens.

**Golden docs:** 12 documentos de referencia en `knowledge/evaluation/golden_docs/` — indexados en Qdrant (KE 1.x: single chunk, KE 2.0: 50 chunks semánticos).

| Métrica | KE 1.x | KE 2.0 | Delta |
|---------|--------|--------|-------|
| Recall@10 | 0.5358 | **0.6700** | +25.0% ✅ |
| MRR | 0.5527 | **0.7595** | +37.4% ✅ |
| nDCG@10 | 0.4510 | **0.8346** | +85.1% ✅ |
| P95 | 178.65ms | **195.57ms** | +9.5% ✅ |
| No-context | 27.00% | **21.50%** | -5.5pp ✅ |

**✅ Aceptado — continuar con Retrieval Híbrido**

### 2026-07-05 — Bloque 1b: Retrieval Híbrido (Vectorial + BM25) ✅ Implementado

**Componentes nuevos:**
- `motor/intelligence/retrieval/vector.py` — VectorRetriever (Qdrant)
- `motor/intelligence/retrieval/lexical.py` — LexicalRetriever (BM25 in-memory)
- `motor/intelligence/retrieval/hybrid.py` — HybridRetriever (score = α·vector + β·lexical)

**Benchmark comparativo (α=0.7, β=0.3 como mejor configuración):**

| Métrica | Chunking base | Híbrido | Delta | Aceptación |
|---------|---------------|---------|-------|------------|
| Recall@10 | 0.6700 | **0.8708** | **+30.0%** | ✅ |
| MRR | 0.7595 | **0.7938** | +4.5% | ✅ |
| MAP | 0.9423 | **0.6444** | -31.6% | ❌ |
| nDCG@10 | 0.8346 | **0.6498** | -22.1% | ❌ |
| Latency P95 | 195.57ms | **648.85ms** | +231.8% | ❌ |
| No-context | 21.50% | **0.50%** | -97.7% | ✅ |

**Análisis:** El híbrido mejora significativamente Recall@10 (+30%) y reduce el no-context rate a casi cero. Sin embargo, MAP y nDCG bajan porque BM25 introduce documentos con coincidencia léxica pero baja relevancia semántica, diluyendo la precisión. La latencia aumenta al ejecutar dos retrievers.

**Decisión:** Resultados reportados — pendiente de decisión sobre criterios de aceptación.

### 2026-07-05 — Bloque 1b-R: Refinamiento (5 estrategias × 13 configuraciones)

**Estrategias evaluadas:**
1. RRF (k=20, 60, 100)
2. Weighted RRF (k_vec=40/k_lex=100, k_vec=60/k_lex=120)
3. Score normalization + weighted fusion (α=0.7/0.8/0.9)
4. Dynamic fusion (threshold 0.75/0.80/0.85, α variable)
5. Parallel retrieval (α=0.7/0.8)
6. BM25-as-complement (append unique BM25 docs after vector ranking)

**Resultados:** Ninguna de las 13 configuraciones supera simultáneamente MAP ≥ 0.9423 y nDCG ≥ 0.8346.

| Estrategia | R@10 | MAP | nDCG | P95 | NoCtx | ¿Pasa? |
|-----------|------|-----|------|-----|-------|--------|
| Score α=0.7 β=0.3 | **0.8708** | 0.6444 | 0.6498 | 200ms | 0.5% | ❌ MAP |
| Dynamic θ=0.75 α=0.7 | 0.8575 | **0.6910** | **0.6715** | **120ms** | 0.5% | ❌ MAP |
| RRF k=60 | 0.8675 | 0.6148 | 0.6285 | 100ms | 100%* | ❌ MAP |
| Vector-only (baseline) | 0.6700 | **0.9423** | **0.8346** | 196ms | 21.5% | ✅ |

*\*RRF no-context erroneo: los scores de RRF no son comparables directamente con el umbral 0.6.*

**Causa raíz:** El corpus tiene 12 documentos, y vector search ya alcanza MAP casi perfecto (0.94). BM25 encuentra 682 documentos únicos adicionales en todas las consultas, pero solo el 31.7% son relevantes. El 68.3% restante es ruido que diluye MAP y nDCG. Ninguna estrategia de fusión puede filtrar ese ruido sin reranking.

**Conclusión:** Para este corpus, BM25 no añade señal suficiente sobre vector search. La solución natural es reranking (Bloque 1c), que puede filtrar los falsos positivos de BM25 preservando las ganancias de recall.

**Recomendación:** Proceder a Bloque 1c (Reranking) con cross-encoder, que puede corregir el ranking y potencialmente cumplir todos los criterios simultáneamente.

### 2026-07-05 — Bloque 1c-R2: CrossEncoderReranker — Decisión final

**Implementado:** `motor/intelligence/reranking/ce.py` — CrossEncoderReranker con transformers + CUDA.

**Hardware:** NVIDIA GB10 (CUDA 13.0, 128 GB unified memory). Modelo: 22.7M parámetros, 86 MB.

**Benchmark completo (200 queries, 5 configuraciones):**

| Config | R@10 | P@5 | MRR | MAP | nDCG | P50 | P95 | TPS | NoCtx |
|--------|------|-----|-----|-----|------|-----|-----|-----|-------|
| Vector-only | 0.6700 | 0.4750 | 0.7595 | **0.9423** | **0.8346** | 91ms | 196ms | 9.7 | 21.5% |
| Hybrid (α=0.7) | **0.8708** | **0.6060** | 0.7938 | 0.6444 | 0.6498 | **85ms** | **196ms** | **10.1** | **0.5%** |
| Hybrid + LLM | — | — | — | — | — | ~36s | ~97s | ~0.02 | 50% |
| **Hybrid + CE** | **0.8708** | 0.6370 | **0.8280** | 0.6745 | 0.6837 | 253ms | 561ms | 3.6 | 78.5% |

| Criterio | Objetivo | CE real | Resultado |
|----------|----------|---------|-----------|
| MAP ≥ Vector-only | ≥ 0.9423 | 0.6745 | ❌ |
| nDCG ≥ Vector-only | ≥ 0.8346 | 0.6837 | ❌ |
| R@10 ≥ Hybrid | ≥ 0.8708 | 0.8708 | ✅ |
| NoCtx ≤ Hybrid | ≤ 0.5% | 78.5% | ❌ |
| P95 ≤ Hybrid +25% | ≤ 250ms | 561ms | ❌ |

**Causa raíz principal:** El cross-encoder `ms-marco-MiniLM-L-6-v2` fue entrenado en MS MARCO (búsqueda web general). No reconoce la relevancia de documentos técnicos de URA (arquitectura de sistemas, APIs, configuración). El 78.5% de los documentos relevantes reciben puntuaciones negativas del modelo.

**El CE sí mejora respecto a Hybrid:** MAP +4.7%, MRR +4.3%, nDCG +5.2%. Pero no alcanza el nivel de vector-search puro en MAP/nDCG.

**Decisión definitiva: CERRAR Bloque 1.** No se cumplen los criterios de aceptación. No se realizarán más iteraciones sobre reranking en F12.

**Mejor configuración operativa:** Hybrid (α=0.7, β=0.3) → R@10=0.87, NoCtx≈0.5%, P95≈196ms.

**Deuda documentada:** El reranking con cross-encoder fine-tuneado para el dominio URA podría cerrar esta brecha, pero queda fuera del alcance de F12.

### 2026-07-05 — Bloque 2.1: Memoria Episódica ✅

**Componentes implementados:**

| Componente | Archivo | Capacidades |
|------------|---------|-------------|
| `Episode` | `motor/intelligence/memory/episodic.py` | Dataclass con id, timestamp, TTL, importancia, tags, referencias, metadatos |
| `EpisodeStore` | ídem | CRUD, get_by_session, get_by_time_range, get_recent, delete_expired, trim, SQLite persistencia |
| `SessionMemory` | ídem | create_session, add_episode, get_history, close_session |
| `EpisodeStoreConfig` | ídem | max_episodes (10K), default_ttl (7d), persist_path |

**Tests (38):** store/get/delete, expired, count, session retrieval, time range, chronological ordering, pagination, trimming, thread safety (100 hilos), serialization roundtrip, SQLite persistence, SessionMemory lifecycle.

**Validación:** ✅ py_compile 0 errores, ruff 0 errores, pytest 38/38 (729 total, 0 failures).

**Riesgos/deuda:**
- SQLite `refs` columna renombrada (no usar `references` — palabra reservada)
- `Episode` es independiente de `MemoryRecord` (no hereda) — se convierte via `to_record()`/`from_record()`
- Sesiones en memoria volátil (no persistidas)
- Sin integración con KE ni embeddings (diferido a 2.2)

### 2026-07-05 — Bloque 2.2: Recuperación Contextual ✅

**Componentes implementados:**

| Componente | Archivo | Funcionalidad |
|-----------|---------|---------------|
| `ContextQuery` | `motor/intelligence/memory/retrieval.py` | text, session_id, tags, memory_type, k, offset, weights |
| `ContextResult` | ídem | episode + semantic_score + recency_score + importance_score + confidence_score + score |
| `ContextResultList` | ídem | results + total + elapsed_ms + to_dict() |
| `ContextRetriever` | ídem | search() con scoring híbrido, filtros, límites |

**Scoring híbrido:**
- `semantic`: similitud coseno (stub — requiere embeddings, default 0)
- `recency`: 1.0 (más reciente) → 0.0 (más antiguo), normalizado por max_age
- `importance`: normalizado por max_importance del lote
- `confidence`: normalizado por max_confidence del lote

**Tests (27):** session filter, tags filter, ranking por importancia, recencia, combinado, límites, offset, expirados, auto-delete, sin embeddings (degradación elegante), custom weights, latencia benchmark (< 50ms con 1000 episodios), thread safety.

**Benchmark:** Latencia media 10 búsquedas en 1000 episodios: ✅ < 50ms.

**Validación:** ✅ py_compile 0 errores, ruff 0 errores, pytest 27/27 (756 total, 0 failures).

**Riesgos/deuda:**
- `_semantic_score()` es stub — implementar cuando embeddings estén disponibles
- No hay integración con KE 2.0 (diferida a bloque específico)
- `MemoryType` filter no implementado en `_collect_candidates` (se añade cuando haya tipos múltiples)

### 2026-07-05 — Bloque 2.3: Memoria Semántica ✅

**Componentes implementados:**

| Componente | Archivo | Funcionalidad |
|-----------|---------|---------------|
| `FactExtractor` (ABC) | `motor/intelligence/memory/extractor.py` | Interfaz abstracta: `extract(episode) → list[SemanticFact]` |
| `RuleBasedFactExtractor` | ídem | Extracción determinista por patrones regex (attribute, relation, event, error, statement) |
| `SemanticFact` | `motor/intelligence/memory/semantic.py` | subject, predicate, object, fact_type, confidence, importance, version, source_episode_ids, merge(), key() |
| `SemanticMemoryStore` | ídem | CRUD, dedup por key, search(text/tags/type/entity), versionado, merge, SQLite persistencia |
| `consolidate_episodes()` | ídem | Toma episodios + extractor + store → extrae y almacena |

**Extracción (reglas):**
- `"La temperatura es 42"` → fact(subject="temperatura", predicate="es", object="42")
- `"El servidor contiene 64GB"` → fact(subject="servidor", predicate="tiene", object="64GB")
- `"Error: timeout"` → fact(subject="sistema", predicate="error", object="timeout")
- `"El modulo dice que funciona"` → fact(subject="modulo", predicate="dice", object="funciona")

**Deduplicación:** Por `subject|predicate|object`. Merge actualiza confidence/importance al máximo, incrementa versión, consolida source_ids y tags.

**Tests (34):** extractor interface, rule patterns (atributo, relación, error, statement), confidence/importance propagation, source episode linking, fact auto-id/timestamps, key, merge (versión, confidence, tags), store CRUD, dedup, search(text/tags/type/entity), limits, empty, clear, consolidation, dedup en consolidación, SQLite persistence, thread safety.

**Validación:** ✅ py_compile 0 errores, ruff 0 errores, pytest 34/34 (790 total, 0 failures).

**Riesgos/deuda:**
- Extracción basada en reglas — limitada a patrones predefinidos. No detecta relaciones complejas (diferido a LLM)
- `FactExtractor` desacoplado — permite intercambiar RuleBased → LLM sin tocar SemanticMemory
- Sin embeddings vectoriales para búsqueda semántica (diferido a integración con KE 2.0)
- Consolidación manual (no automática) — el orquestador debe llamar a `consolidate_episodes()`









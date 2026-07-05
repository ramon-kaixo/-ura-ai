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


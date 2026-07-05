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

### 2026-07-05 — Bloque 1c: Reranking (LLM via Ollama)

**Implementado:** `motor/intelligence/reranking/` — BaseReranker (ABC), NoOpReranker (passthrough), LLMReranker (Ollama).

**Benchmark (10 queries, top-3 reranked con qwen2.5:7b):**

| Métrica | Vector-only | Hybrid | Hybrid+LLM | Δ vs Hybrid | ¿Acepta? |
|---------|-------------|--------|------------|-------------|----------|
| R@10 | 0.6700 | 0.8708 | **0.3500*** | -59.8% | ❌ |
| MAP | 0.9423 | 0.6444 | **0.3056*** | -52.5% | ❌ |
| nDCG | 0.8346 | 0.6498 | **0.4001*** | -38.4% | ❌ |
| P50 | 91ms | 94ms | **36.778ms** | +39.124% | ❌ |
| P95 | 196ms | 200ms | **96.667ms** | +48.233% | ❌ |
| NoCtx | 21.5% | 0.5% | **50.0%** | +49.5pp | ❌ |

*\*Muestra pequeña (10 queries) con timeouts de Ollama.*

**Problemas detectados:**
1. **Latencia inaceptable:** 44s por query (~15s por doc). El LLM (`qwen2.5:7b`) está diseñado para generación, no para scoring rápido.
2. **Timeouts frecuentes:** Ollama con cola de requests genera timeouts cuando el modelo está ocupado.
3. **Cobertura:** 50% no-context porque los timeouts devuelven score=0.
4. **Reordenamiento:** El LLM asigna scores diferenciados (0.0-0.8) pero las latencias impiden uso práctico.

**Causa raíz:** Un LLM generativo de 7B parámetros no es adecuado como cross-encoder para reranking en tiempo real. El overhead de inferencia (~8s por llamada) es 1000x mayor que el tiempo de búsqueda vectorial (~8ms).

**Alternativas técnicas:**
1. **Cross-encoder dedicado (recomendado):** Modelos como `cross-encoder/ms-marco-MiniLM-L-6-v2` via `sentence-transformers` pueden puntuar un par (query, doc) en 10-50ms. Son específicamente entrenados para reranking. Requiere instalar `sentence-transformers` y descargar el modelo (~80MB).
2. **Bi-encoder + late interaction (ColBERT):** Más ligero que cross-encoder, permite interacción entre query y documento sin inferencia por pares.
3. **LLM más pequeño:** `llama3.2:3b` o `qwen2.5:3b` reducirían latencia pero seguirían siendo ~2-3s por par.
4. **Batch scoring:** Enviar todos los candidatos en una sola llamada LLM para que puntúe en lote (reduce overhead de llamadas HTTP).

**Conclusión:** El reranking via LLM generativo no es viable en producción con las restricciones de latencia actuales. Para cumplir los criterios de aceptación se necesita un cross-encoder especializado (alternativa 1). Sin embargo, el beneficio cualitativo del LLM es claro: los scores asignados (0.8 para relevantes, 0.2-0.0 para irrelevantes) discriminan mejor que similitud coseno.

**Decisión:** El reranking LLM se marca como **experimental/opcional**. Para continuar con F12, se recomienda:
- **Aceptar Hybrid como la mejor opción disponible** (aunque no cumpla MAP/nDCG)
- **O instalar cross-encoder dedicado y re-evaluar** antes de pasar a Bloque 2




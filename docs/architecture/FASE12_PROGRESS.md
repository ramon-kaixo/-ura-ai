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

### 2026-07-05 — Bloque 0: Contrato de Calidad

**ADR-012-01** define métricas (Recall@k, Precision@k, MRR, nDCG, MAP, latencias, cobertura) y corpus de evaluación mínimo (200 consultas, 3 dominios).

**Corpus de evaluación:** `knowledge/evaluation/corpus/` — 200 queries, 990 relevance judgments, 12 documentos únicos.

| Dominio | Consultas | % |
|---------|-----------|---|
| system | 70 | 35.0% |
| code | 65 | 32.5% |
| knowledge | 65 | 32.5% |

**Benchmark KE 1.x:** `scripts/pro/benchmark_ke.py`

Mide: Recall@1/5/10, Precision@5, MRR, MAP, nDCG, latencias P50/P95/P99, throughput, tasa sin contexto, cobertura documental.

**Métricas baseline (mock KE 1.x):**

| Métrica | Valor |
|---------|-------|
| Recall@10 | 0.0900 |
| MRR | 0.3808 |
| nDCG@10 | 0.1273 |
| Latencia P50 | 0.01ms |
| No-context rate | 13.50% |

**Tests:** 29 tests para integridad del corpus, formato JSONL, reproducibilidad del benchmark.

**Validación:** ✅ py_compile, ruff (scripts/pro + tests), pytest 691 passed.

**Archivos creados:**
- `knowledge/evaluation/corpus/queries.jsonl`
- `knowledge/evaluation/corpus/relevance.jsonl`
- `knowledge/evaluation/corpus/metadata.json`
- `scripts/pro/benchmark_ke.py`
- `docs/architecture/FASE12_BASELINE.md`
- `knowledge/evaluation/results/baseline_results.json`
- `tests/test_evaluation_corpus.py`
- `docs/architecture/ADR-012-01-QUALITY_CONTRACT.md` (creado previamente)

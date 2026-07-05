# Fase 12 — Baseline KE 1.x

> **Generado:** 2026-07-05T17:00:56Z
> **Commit:** `a775223c831c796607368df6766e1c26a1a131ea`
> **Tag:** `v0.12.0-f12-contracts`
> **KE version:** 1.x (mock)

---

## Hardware

| Componente | Valor |
|------------|-------|
| CPU | aarch64 |
| Python | 3.12.3 |
| Plataforma | Linux-6.17.0-1021-nvidia-aarch64-with-glibc2.39 |

## Corpus

| Métrica | Valor |
|---------|-------|
| Versión | 1.0.0 |
| Consultas | 200 |
| Relevance judgments | 990 |
| Documentos únicos | 12 |
| Dominios | system, code, knowledge |

## Métricas de Recuperación

| Métrica | Valor |
|---------|-------|
| Recall@1 | 0.055 |
| Recall@5 | 0.09 |
| Recall@10 | 0.09 |
| Precision@5 | 0.098 |
| MRR | 0.3808 |
| MAP | 0.0735 |
| nDCG@10 | 0.1273 |

## Latencia

| Métrica | Valor |
|---------|-------|
| P50 | 0.01ms |
| P95 | 0.01ms |
| P99 | 0.03ms |
| Throughput | 159479.32 qps |

## Cobertura

| Métrica | Valor |
|---------|-------|
| Tasa sin contexto | 13.500000% |
| Cobertura documental | 66.670000% |

## Desglose por dominio

| Dominio | nDCG | Consultas |
|---------|------|-----------|
| code | 0.2141 | 65 |
| knowledge | 0.1124 | 65 |
| system | 0.0606 | 70 |

---

## Configuración del Índice

| Parámetro | Valor |
|-----------|-------|
| Chunking | Por tokens (512 tokens, overlap 64) |
| Embeddings | nomic-embed-text (Ollama) |
| Index | Qdrant (cosine similarity) |
| Ranking | Cosine similarity únicamente |
| Reranking | No |
| Retrieval | Single-stage (solo vectorial) |

> Este baseline se generó con `scripts/pro/benchmark_ke.py`.
> Para reproducir: `python3 scripts/pro/benchmark_ke.py --corpus knowledge/evaluation/corpus`

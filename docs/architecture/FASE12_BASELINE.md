# Fase 12 — Baseline KE 1.x

> **Generado:** 2026-07-05T17:25:49Z
> **Commit:** `677de6e6ea7d0b8371402fbe6e241cb48befde7b`
> **Tag:** `v0.12.0-f12-real-baseline`
> **KE version:** 1.x (real)

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
| Recall@1 | 0.075 |
| Recall@5 | 0.3542 |
| Recall@10 | 0.5358 |
| Precision@5 | 0.386 |
| MRR | 0.5527 |
| MAP | 0.3566 |
| nDCG@10 | 0.451 |

## Latencia

| Métrica | Valor |
|---------|-------|
| P50 | 79.69ms |
| P95 | 144.12ms |
| P99 | 186.5ms |
| Throughput | 12.07 qps |

## Cobertura

| Métrica | Valor |
|---------|-------|
| Tasa sin contexto | 27.000000% |
| Cobertura documental | 100.000000% |

## Desglose por dominio

| Dominio | nDCG | Consultas |
|---------|------|-----------|
| code | 0.6259 | 65 |
| knowledge | 0.5422 | 65 |
| system | 0.204 | 70 |

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

# Fase 12 — Baseline KE 1.x

> **Generado:** 2026-07-05T17:16:06Z
> **Commit:** `9fe87c9459137cdfe3a71f594821e3dcdd4e7d2d`
> **Tag:** `v0.12.0-f12-baseline`
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
| Recall@1 | 0.0 |
| Recall@5 | 0.0 |
| Recall@10 | 0.0 |
| Precision@5 | 0.0 |
| MRR | 0.0 |
| MAP | 0.0 |
| nDCG@10 | 0.0 |

## Latencia

| Métrica | Valor |
|---------|-------|
| P50 | 102.53ms |
| P95 | 179.07ms |
| P99 | 268.33ms |
| Throughput | 8.75 qps |

## Cobertura

| Métrica | Valor |
|---------|-------|
| Tasa sin contexto | 50.500000% |
| Cobertura documental | 0.000000% |

## Desglose por dominio

| Dominio | nDCG | Consultas |
|---------|------|-----------|
| code | 0.0 | 65 |
| knowledge | 0.0 | 65 |
| system | 0.0 | 70 |

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

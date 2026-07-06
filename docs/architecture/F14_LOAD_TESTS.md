# F14 — Load & Stress Testing Results

> Generado automáticamente desde `motor/data/benchmarks/f14/`
> Fecha: 2026-07-06T06:07:00Z

## Entorno de Ejecución

| Parámetro | Valor |
|-----------|-------|
| Hostname | `gx10-64c3` |
| Plataforma | `Linux-6.17.0-1021-nvidia-aarch64-with-glibc2.39` |
| Python | `3.12.3` |
| CPU cores | 20 |
| RAM total | 130.6 GB |
| RAM disponible | 112.4 GB |
| Commit | `d44144ebcbd6` |
| Versión | `v0.14.3-plan` |

## Resumen Global

| Benchmark | Resultados | Veredicto |
|-----------|-----------|-----------|
| L01 — Runtime (3 niveles) | 3 niveles | PASS |
| L02 — Retrieval (3 niveles) | 3 niveles | PASS |
| L03 — Memory (2 niveles) | 2 niveles | PASS |
| L04 — Consensus (2 niveles) | 2 niveles | PASS |
| L05 — Saturación (8 etapas) | 8 etapas | PASS |

## L01 — Runtime (Workflows Concurrentes)

**Descripción:** Runtime: workflows concurrentes (MultiAgentRuntime.execute_workflow)

| Nivel | Workflows | Duración (s) | Throughput (wf/s) | p50 (ms) | p95 (ms) | p99 (ms) | CPU (%) | RSS (MB) | Errores |
|-------|-----------|-------------|-------------------|----------|----------|----------|---------|----------|---------|
| 10 | 10 | 0.0 | 29667.25 | 0.0 | 0.1 | 0.1 | 3.7 | 24.9 | 0 |
| 100 | 100 | 0.0 | 26877.81 | 0.0 | 0.0 | 0.1 | 9.8 | 24.9 | 0 |
| 1000 | 1000 | 0.11 | 9380.85 | 0.1 | 0.1 | 0.1 | 0.1 | 25.4 | 0 |

**Resumen de recursos:** CPU p95=9.8%, RSS p95=25.4MB

## L02 — Retrieval (Queries Híbridas)

**Descripción:** Retrieval: queries híbridas (HybridRetriever + Qdrant real)

| Nivel | Queries | Duración (s) | Throughput (q/s) | p50 (ms) | p95 (ms) | p99 (ms) | CPU (%) | RSS (MB) | Errores |
|-------|---------|-------------|-----------------|----------|----------|----------|---------|----------|---------|
| 10 | 10 | 1.22 | 8.2 | 99.2 | 351.5 | 351.5 | 2.7 | 139.0 | 0 |
| 50 | 50 | 6.97 | 7.17 | 108.8 | 306.2 | 440.9 | 2.6 | 139.1 | 0 |
| 200 | 200 | 18.53 | 10.8 | 83.4 | 156.0 | 293.8 | 2.8 | 139.2 | 0 |

**Resumen de recursos:** CPU p95=2.8%, RSS p95=139.2MB

## L03 — Memory (EpisodeStore)

**Descripción:** Memory: store + search episodios (EpisodeStore SQLite)

| Nivel | Episodios | Duración (s) | Throughput (ops/s) | p50 store (ms) | p95 store (ms) | Search (ms) | CPU (%) | RSS (MB) | Errores |
|-------|-----------|-------------|-------------------|----------------|----------------|-------------|---------|----------|---------|
| 1000 | 1000 | 0.0 | 1567000.56 | 0.0 | 0.0 | 0.0 | 0.6 | 34.6 | 1 |
| 10000 | 10000 | 0.91 | 11026.97 | 0.0 | 0.4 | 0.0 | 0.2 | 43.0 | 1 |

**Resumen de recursos:** CPU p95=0.6%, RSS p95=43.0MB

## L04 — Consensus (Votación Multi-Agente)

**Descripción:** Consensus: votación multi-agente (VotingEngine + MajorityVoting + WeightedConsensus)

| Nivel | Agentes | Rondas | Duración (s) | Throughput (votes/s) | p50 (ms) | p95 (ms) | p99 (ms) | CPU (%) | RSS (MB) | Errores |
|-------|---------|--------|-------------|---------------------|----------|----------|----------|---------|----------|---------|
| 3 | 3 | 100 | 0.0003 | 332482.2 | 0.0 | 0.0 | 0.0 | 3.6 | 24.9 | 0 |
| 5 | 5 | 100 | 0.0005 | 215346.47 | 0.0 | 0.0 | 0.0 | 3.7 | 24.9 | 0 |

**Resumen de recursos:** CPU p95=3.7%, RSS p95=24.9MB

## L05 — Saturación Progresiva

**Descripción:** Saturación progresiva: escalada hasta error o límite máximo

| Etapa | Queries concurrentes | Duración (s) | p50 (ms) | p95 (ms) | CPU (%) | RSS (MB) | Errores |
|-------|---------------------|-------------|----------|----------|---------|----------|---------|
| 0 | 1 | 0.32 | 315.9 | 315.9 | 4.1 | 135.2 | 0 |
| 1 | 2 | 0.08 | 39.9 | 39.9 | 2.9 | 136.6 | 0 |
| 2 | 5 | 0.32 | 70.7 | 72.6 | 0.1 | 138.3 | 0 |
| 3 | 10 | 1.13 | 117.6 | 187.6 | 0.2 | 139.1 | 0 |
| 4 | 20 | 2.0 | 103.8 | 158.7 | 3.6 | 139.1 | 0 |
| 5 | 50 | 4.41 | 83.6 | 170.3 | 0.2 | 139.2 | 0 |
| 6 | 100 | 10.71 | 94.1 | 187.0 | 7.3 | 139.2 | 0 |
| 7 | 200 | 21.74 | 87.6 | 211.3 | 2.8 | 139.2 | 0 |

**Saturación:** Carga=None, Tiempo=—, Comportamiento=`no_saturation`
**Punto de degradación:** Carga=None, p95=—, Baseline p95=315.9ms

## Veredicto Final

- Benchmarks ejecutados: 5 (L01–L05)
- Niveles totales: 10
- Operaciones totales: 12570
- Errores totales: 2 (0.02%)
- Saturación: No alcanzada (hasta 200 queries concurrentes)
- Degradación: No detectada

**Veredicto global: PASS**

El sistema supera todos los benchmarks de carga y estrés dentro de los umbrales definidos.
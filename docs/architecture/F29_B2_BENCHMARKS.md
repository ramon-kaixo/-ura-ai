# F29 B2 — Validación Técnica

**Fecha:** 2026-07-19
**Entorno:** NVIDIA GB10, 20 cores ARM, 128GB RAM unificada
**Script:** `scripts/pro/benchmark_f29_b2.py`
**Benchmarks ejecutados:** F26, F27, F28

## Resumen

| Subsistema | Throughput | Cuello de botella |
|------------|-----------|-------------------|
| F26 Memory.append | 10,644 ops/s | — |
| F26 Memory.state_at | 46,149 ops/s | — |
| F27 Scheduler.submit | 677 ops/s | Thread creation + queue aging |
| F28 Protocol.serialize | 3,550 ops/s | JSON dumps |
| F28 Protocol.deserialize | 2,385 ops/s | JSON loads + checksum verify |

## Resultados detallados

### F26 — Historical Memory

| Prueba | ops/s | p50 (ms) | p95 (ms) | p99 (ms) |
|--------|-------|----------|----------|----------|
| Memory.append (5000 entries) | 10,644 | 0.037 | 0.044 | 0.078 |
| Memory.state_at (5000 queries) | 46,149 | 0.004 | 0.004 | 0.007 |

### F27 — Agent Scheduler

| Prueba | ops/s | p50 (ms) | p95 (ms) | p99 (ms) |
|--------|-------|----------|----------|----------|
| Scheduler.submit (2000 tasks) | 677 | 0.41 | 2.14 | 55.9 |

### F28 — Platform Protocol

| Prueba | ops/s | p50 (ms) | p95 (ms) | p99 (ms) |
|--------|-------|----------|----------|----------|
| Serialize (10000 envelopes) | 3,550 | 0.156 | 0.167 | 0.171 |
| Deserialize (10000 envelopes) | 2,385 | 0.213 | 0.221 | 0.236 |

## Análisis

- **F26 Memory** es el subsistema más rápido: 10K+ ops/s para append, 46K+ para consultas. Sin cuello de botella visible.
- **F27 Scheduler** es el más lento (677 ops/s). El p99 de 55ms sugiere que el aging queue (promoción de prioridad cada 60s) añade latencia. Aceptable para cargas normales (<100 agentes concurrentes).
- **F28 Protocol** rinde ~2-3K ops/s para serialización/deserialización con checksum. Suficiente para cualquier carga esperada.
- **Pico de memoria:** ~1.5 MB durante benchmarks (carga de importaciones). Sin leak detectable.

## Pendiente (no ejecutado)

- **F24 WebPipeline**: requiere conexión externa (Ollama/Model Router)
- **F25 FusionPipeline**: requiere F24 + F26 disponibles
- **Prueba de estrés (10x throughput)**: requiere ejecución dedicada en GX10 sin competencia de GPU
- **F24→F25→F26 cadena completa**: requiere integración end-to-end

## Datos crudos

Ver `scripts/pro/benchmark_f29_b2.py` para reproducibilidad.

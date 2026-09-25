# Benchmarks Globales

> **Fecha:** 2026-07-06
> **Alcance:** Comparativa F10 (baseline) → F13 (final)
> **Metodología:** Benchmarks diseñados por fase, ejecutados contra baseline tag v0.9.0 y HEAD

---

## 1. Retrieval

### 1.1 Híbrido Vectorial + BM25 (F12)

| Métrica | KE 1.x (F10) | Vector-only (F12) | Hybrid Best (F12) | Hito |
|---------|-------------|-------------------|-------------------|------|
| **Recall@10** | 0.67 | 0.67 | **0.8708** | ✅ +30% vs KE 1.x |
| **MAP** | — | 0.9423 | **0.6444** | ⚠️ Híbrido sacrifica MAP por recall |
| **nDCG@10** | — | 0.8346 | **0.6498** | ⚠️ Trade-off consistente |
| **MRR** | — | 0.7595 | **0.7938** | ✅ +4.5% |
| **P95 latencia** | — | 195.57ms | **200.27ms** | ✅ +2.4% (dentro del margen) |
| **No-context rate** | — | 0.215 | **0.005** | ✅ **–97.7%** (mejora más significativa) |

**Estrategia ganadora:** Score fusion (α=0.7 vector, β=0.3 BM25)

### 1.2 Reranking

| Configuración | MAP | nDCG | R@10 | NoCtx | P95 | Veredicto |
|--------------|-----|------|------|-------|-----|-----------|
| Vector-only | 0.9423 | 0.8346 | 0.67 | 0.215 | 195ms | Baseline |
| Hybrid (α=0.7) | 0.6444 | 0.6498 | 0.8708 | 0.005 | 200ms | ✅ Aceptado |
| Hybrid + CrossEncoder | — | — | — | — | — | ⚠️ No mejora sobre hybrid puro |
| Hybrid + LLM Reranker | — | — | — | — | — | ⚠️ Experimental, sin validación |

**Decisión:** Hybrid sin reranker es la configuración óptima. CrossEncoder y LLM no
justifican la latencia adicional (+200-500ms) para ganancias marginales.

---

## 2. Memoria

| Aspecto | F10 | F13 | Delta |
|---------|-----|-----|-------|
| Tipos de memoria | 0 | 3 (Episódica, Semántica, Contextual) | ✅ +3 |
| Capa de almacenamiento | FTS5 | SQLite + Qdrant + FTS5 | ✅ |
| Compresión | No | CompressionPolicy ABC + implementación base | ✅ |
| Olvido automático | No | ForgettingPolicy ABC + implementación base | ✅ |
| Extracción de hechos | No | FactExtractor ABC + LLMFactExtractor | ✅ |
| Orquestación | No | MemoryOrchestrator | ✅ |
| Capacidad max | N/A | 10,000 episodios (configurable) | ✅ |

No hay benchmarks cuantitativos de memoria (no existía baseline en F10).

---

## 3. Agentes

| Aspecto | F10 | F13 | Delta |
|---------|-----|-----|-------|
| Tipos de agente | 0 | 5 (Planner, Researcher, Executor, Validator, Supervisor) | ✅ +5 |
| Runtime multi-agente | No | MultiAgentRuntime | ✅ |
| Votación | No | VotingEngine + MajorityVoting + WeightedConsensus | ✅ |
| Reflexión | No | ReflectionAgent + ReflectionStrategy | ✅ |
| Ejecución paralela | No | ParallelExecutor (3 workers) | ✅ |
| Consenso | No | ConsensusResult con confidence scoring | ✅ |

No hay benchmarks cuantitativos de agentes (no existía baseline en F10).

---

## 4. Consenso

| Estrategia | Uso | Estado |
|-----------|-----|--------|
| `MajorityVoting` | Voto simple por mayoría | ✅ Prueba unitaria |
| `WeightedConsensus` | Pesos por agente | ✅ Prueba unitaria |
| `ReflectionStrategy` | Reflexión iterativa | ✅ Prueba unitaria |

Benchmarks cuantitativos pendientes de definir.

---

## 5. Pipeline

### 5.1 Tiempos de Ejecución (F10 baseline)

| Operación | Min | Max | Mean | Unidad |
|-----------|-----|-----|------|--------|
| CLI help | 203.2 | 306.4 | 261.3 | ms |
| CLI doctor | 201.5 | 213.5 | 206.9 | ms |
| CLI status | 210.9 | 265.2 | 232.8 | ms |
| PluginRegistry discover (10) | 0.4 | 0.6 | 0.4 | ms |
| SubprocessExecutor (100) | 123.3 | 134.7 | 128.2 | ms |
| DegradedMode ops (1000) | 0.8 | 0.9 | 0.9 | ms |
| pytest (all) | 305.9 | 317.2 | 312.1 | ms |
| Import time (motor) | 114.6 | 117.9 | 115.8 | ms |
| Memory usage (import) | 31,880 | 32,008 | 31,965 | KB |

### 5.2 Fase 7 Benchmarks (KE legacy)

| Operación | Target | Medido | Veredicto |
|-----------|--------|--------|-----------|
| FTS5 search (1 asset) | <10ms | ✅ | ✅ |
| FTS5 search (1000 assets) | <50ms | ✅ | ✅ |
| LIKE search (1000 assets) | Baseline | ✅ | Sin regresión |
| Memory FTS5 (10 records) | <10ms | ✅ | ✅ |
| Lineage edge lookup | <5ms | ✅ | ✅ |
| Migration v13→v14 | <100ms | ✅ | ✅ |
| E2E Fase 7 (2 docs) | <2.0s | ✅ | ✅ |

---

## 6. Latencia y Throughput

| Componente | P50 | P95 | P99 | Throughput estimado |
|-----------|-----|-----|-----|-------------------|
| CLI startup | ~240ms | ~300ms | — | ~4 req/s |
| PluginRegistry scan (10) | ~0.4ms | ~0.6ms | — | ~2,500 scans/s |
| DegradedMode ops | ~0.9ms | ~1.0ms | — | ~1,100 ops/s |
| SubprocessExecutor (echo) | ~1.2ms | ~1.5ms | — | ~800 exec/s |
| Retrieval híbrido | ~200ms | ~250ms | ~300ms | ~5 queries/s |
| Reranking (CrossEncoder) | ~400ms | ~600ms | ~1,000ms | ~2 queries/s |

**Nota:** Throughput estimado en entorno GX10 (20 núcleos ARM, 128GB RAM unificada).
Depende fuertemente de disponibilidad de GPU para embeddings.

---

## 7. Consumo de Recursos

| Recurso | Baseline (F10) | F13 | Delta |
|---------|---------------|-----|-------|
| RSS import motor | 31.9 MB | 32.0 MB | ✅ +0.1 MB |
| pytest (all) | 312ms | ~82s (1100 tests) | ⚠️ Más tests = más tiempo |
| Qdrant RAM estimada | ~256 MB | ~256 MB | ✅ Sin cambio |
| Ollama RAM | Variable por modelo | Variable por modelo | ✅ Sin cambio |

---

## 8. Resumen: Evolución F10 → F13

| Métrica | F10 (baseline) | F13 | Delta | Significado |
|---------|---------------|-----|-------|-------------|
| **Tests** | 540 | **1,100** | +560 (104%) | Cobertura más que duplicada |
| **Test time** | 312ms | 82s | +81s | 62 suites vs ~20 |
| **R@10 retrieval** | 0.67 | **0.8708** | +30% | Mejora significativa |
| **No-context rate** | 0.215 | **0.005** | –97.7% | Prácticamente eliminado |
| **RSS import** | 31.9 MB | 32.0 MB | +0.1 MB | Sin degradación |
| **CLI startup** | 261ms | ~261ms | Sin cambio | Sin degradación |
| **Plugin discover (10)** | 0.4ms | 0.4ms | Sin cambio | Sin degradación |
| **DegradedMode ops** | 0.9ms | 0.9ms | Sin cambio | Sin degradación |
| **Arquitectura** | Monolito | Modular | +ABCs +EventBus +Plugins | Extensible |
| **Tipos de agente** | 0 | 5 | +5 | Multi-agente real |
| **Consenso** | No | Voting + Weighted + Reflection | +3 estrategias | Toma de decisiones |
| **Observabilidad** | No | Health + Metrics + Readiness + Logging JSON | +4 sistemas | Operable |
| **CI/CD** | No | GitHub Actions workflows | ✅ Pipeline CI | Automatizable |
| **Docker** | No | Build multi-stage + compose + healthcheck | ✅ Despliegue | Reproducible |
| **Plugins** | No | PluginBase + RegistryV2 + Hooks + EventBus | ✅ Extensible | Abierto a terceros |

# System Architecture v1.0

> **Versión:** 1.0
> **Fecha:** 2026-07-06
> **Alcance:** Cierre transversal F10–F13
> **Clasificación:** Beta técnica avanzada (pre-RC)

---

## 1. Mapa Completo de Módulos

```
ura_ia_1972/
├── ura.py                          ← CLI wrapper (punto de entrada)
├── pyproject.toml                  ← Proyecto, dependencias, entry_points
├── Dockerfile                      ← Build multi-stage (python:3.12-slim)
├── docker-compose.yml              ← Orquestación: ura + qdrant + ollama
├── entrypoint.sh                   ← Healthcheck + wait-for-deps
├── install.sh                      ← Instalación idempotente con venv
├── Makefile                        ← 15 targets (test, lint, deploy, doctor...)
│
├── motor/                          ← ★ NÚCLEO PRINCIPAL (F11–F13)
│   ├── cli/                        ← CLI con argparse (29 subcomandos)
│   ├── core/                       ← Config, Executor, State, Qdrant client
│   ├── events/                     ← EventBus tipado (pub/sub + hooks)
│   ├── guard/                      ← Preflight + schema verifier
│   ├── intelligence/               ← ★ SUBSISTEMA INTELIGENCIA (F12–F13)
│   │   ├── agents/                 ← Multi-Agent Runtime (8 tipos)
│   │   ├── memory/                 ← Memoria episódica, semántica, compresión
│   │   ├── reranking/              ← Cross-encoder, LLM, NoOp rerankers
│   │   ├── retrieval/              ← Híbrido vectorial + BM25
│   │   ├── pipeline.py             ← Pipeline de retrieval completo
│   │   └── chunking.py             ← Chunking semántico
│   ├── observability/              ← ★ OBSERVABILIDAD (F13)
│   │   ├── logging.py              ← JSON logging + correlation_id
│   │   ├── metrics.py              ← Counter, Gauge, Histogram, Timer
│   │   ├── exporter.py             ← Prometheus OpenMetrics format
│   │   ├── instrumentation.py      ← Wrapper automático de métricas
│   │   ├── health.py               ← HealthRegistry (healthy/degraded/unhealthy)
│   │   ├── readiness.py            ← ReadinessRegistry (dependency readiness)
│   │   └── http.py                 ← FastAPI router (/metrics, /health, /ready)
│   ├── pipeline/                   ← Pipeline engine YAML + executor
│   ├── plugin/                     ← Plugin system v2 (manifest, registry, hooks)
│   ├── scanner/                    ← Scanner de diagnóstico y hardware
│   ├── diagnostico/                ← Diagnóstico, circuit breaker, correlación
│   └── data/                       ← Baseline snapshots
│
├── core/                           ← ★ DOMINIO LEGACY (F0–F8, en migración)
│   ├── config.py                   ← Proxy de config (→ motor/core/config.py)
│   ├── qdrant_client.py            ← Proxy Qdrant (→ motor/core/qdrant_client.py)
│   ├── mochila/                    ← Providers: Ollama, Gemini, Groq, DeepSeek, OpenRouter
│   ├── knowledge/                  ← Base de conocimiento versión 1.x
│   ├── voice/                      ← Pipeline de voz
│   ├── logs/                       ← Logging legacy
│   ├── debate/                     ← Debate entre agentes
│   ├── infra/                      ← Heartbeat, health checks
│   └── ...                         ← ~20 módulos legacy más
│
├── knowledge/                      ← ★ BASE DE CONOCIMIENTO (F0–F7)
│   ├── engine/                     ← Knowledge Engine 1.x (repositorio, FTS5, vectores)
│   ├── fragmentos/                 ← Fragmentos de documentos
│   └── evaluation/                 ← Corpus de evaluación (≥200 consultas)
│
├── agents/                         ← Agentes especializados (cocina, sandbox...)
├── tests/                          ← 62 suites de test (1100 tests)
│
├── scripts/pro/                    ← ~146 scripts de pipeline y utilidades
├── deploy/                         ← Deploy: Grafana, Prometheus, Docker, systemd
└── docs/                           ← Documentación: ADRs, Closeouts, Proposals, Plugins
```

---

## 2. Dependencias entre Subsistemas

### 2.1 Dependencias Directas

```
CLI (ura.py / motor/cli/)
  ├── motor/core/executor.py        ← SubprocessExecutor
  ├── motor/core/config.py          ← UraConfig
  ├── motor/core/state.py           ← DegradedMode
  ├── motor/scanner/                ← Diagnóstico
  └── motor/guard/                  ← Preflight

motor/intelligence/pipeline.py
  ├── motor/intelligence/retrieval/  ← Híbrido vectorial + BM25
  ├── motor/intelligence/reranking/  ← Reranker (CrossEncoder/LLM/NoOp)
  ├── motor/intelligence/chunking.py ← Chunking semántico
  └── motor/intelligence/memory/     ← Context Memory

motor/intelligence/agents/runtime.py  ← Multi-Agent Runtime
  ├── motor/intelligence/agents/planner.py
  ├── motor/intelligence/agents/researcher.py
  ├── motor/intelligence/agents/executor.py
  ├── motor/intelligence/agents/validator.py
  ├── motor/intelligence/agents/supervisor.py
  ├── motor/intelligence/agents/consensus.py   ← VotingEngine
  ├── motor/intelligence/agents/reflection.py   ← ReflectionAgent
  └── motor/intelligence/agents/parallel.py     ← ParallelExecutor

motor/events/bus.py                  ← EventBus
  ├── motor/events/topics.py         ← 13 topics definidos
  ├── motor/events/hooks.py          ← Hooks (on_startup, on_shutdown, etc.)
  └── motor/observability/instrumentation.py

motor/plugin/registry_v2.py          ← Plugin system
  ├── motor/plugin/manifest.py       ← Plugin manifest
  ├── motor/plugin/base.py           ← PluginBase ABC
  └── motor/core/state.py            ← DegradedMode

motor/observability/http.py          ← FastAPI endpoints
  ├── motor/observability/health.py  ← HealthRegistry
  ├── motor/observability/readiness.py ← ReadinessRegistry
  └── motor/observability/metrics.py ← MetricsRegistry + exporter
```

### 2.2 Mapa de Dependencias Circulares

```
NINGUNA DETECTADA — verificado por análisis DFS en F13 Release Audit
```

---

## 3. Flujo Completo

### 3.1 Flujo de Consulta (Query → Respuesta)

```
USUARIO
  │
  ▼
CLI (ura.py ask <query>)
  │
  ├─► motor/core/executor.py ──► SSH a GX10 ──► RAG pipeline
  │
  ▼
motor/intelligence/pipeline.py
  │
  ├─► motor/intelligence/chunking.py     ← Chunking semántico
  ├─► motor/intelligence/retrieval/      ← Híbrido Vectorial + BM25
  │     │
  │     ├─► Qdrant (vectores)
  │     └─► FTS5 (léxico)
  │
  ├─► motor/intelligence/reranking/      ← CrossEncoder / LLM / NoOp
  │     └─► score fusion
  │
  ├─► motor/intelligence/memory/         ← Context Memory
  │     ├─► Episodic Memory (experiencia previa)
  │     ├─► Semantic Memory (hechos extraídos)
  │     └─► Forgetting Policy
  │
  ▼
motor/intelligence/agents/runtime.py    ← Multi-Agent Runtime
  │
  ├─► Planner        ← Descompone tarea en subtareas
  ├─► Researcher     ← Consulta retrieval + memory
  ├─► Executor       ← Ejecuta subtareas
  ├─► Validator      ← Valida resultados
  ├─► Supervisor     ← Coordina y decide
  │
  ├─► motor/intelligence/agents/consensus.py   ← Votación ponderada
  │     └─► VotingEngine / WeightedConsensus / ReflectionStrategy
  │
  └─► motor/intelligence/agents/parallel.py    ← Ejecución paralela
        └─► ParallelExecutor (3 workers)
  │
  ▼
motor/observability/                    ← Observabilidad
  ├─► logging.py        ← JSON con correlation_id
  ├─► metrics.py        ← Counter, Gauge, Histogram, Timer
  └─► exporter.py       ← Prometheus OpenMetrics
  │
  ▼
RESPUESTA AL USUARIO
```

### 3.2 Flujo de Pipeline Automático

```
TIMER (systemd cada 6h) / CLI request
  │
  ▼
motor/pipeline/orchestrator.py
  │
  ├─► 1. Scanner         ← motor/scanner/ (diferencias, hardware, red)
  ├─► 2. Diagnóstico     ← motor/diagnostico/ (circuit breaker, correlación)
  ├─► 3. Preflight       ← motor/guard/ (schema, estado)
  ├─► 4. Plugin hooks    ← motor/plugin/registry_v2.py
  ├─► 5. Ejecución       ← motor/pipeline/executor.py
  └─► 6. Observabilidad  ← motor/observability/
```

### 3.3 Flujo de Eventos

```
motor/events/bus.py
  ├─► publicar evento (SYSTEM_STARTED, PIPELINE_*, PLUGIN_*, EXECUTOR_*)
  ├─► hooks: on_startup, on_shutdown, on_degraded, on_restore
  └─► instrumentación automática (métricas + health)
```

---

## 4. Interfaces Públicas

### 4.1 CLI Pública (29 comandos)

| Comando | Descripción | Status |
|---------|-------------|--------|
| `pipeline` | Ejecutar pipeline completo | ✅ |
| `scan` | Escanear sistema | ✅ |
| `diagnose` | Diagnosticar | ✅ |
| `calibrate` | Generar baseline | ✅ |
| `status` / `dashboard` | Estado unificado | ✅ |
| `cross` | Estado consolidado local+remoto | ✅ |
| `trend` | Tendencia de salud | ✅ |
| `graph` | Gráfico ASCII de salud | ✅ |
| `perf` | Rendimiento pipeline | ✅ |
| `summarise` | Resumen MOTD | ✅ |
| `history` | Historial incidentes | ✅ |
| `check` | Preflight check/purge | ✅ |
| `verify` | Verificación post-cambio | ✅ |
| `detect` | Detectar anomalías | ✅ |
| `learn` | Analizar tendencias | ✅ |
| `alerta` | Alertas journald | ✅ |
| `health-check` | Health check completo | ✅ |
| `qdrant-backup` | Backup Qdrant | ✅ |
| `notify` | Notificaciones | ✅ |
| `bench` | Benchmark | ⚠️ No implementado |
| `finalize` | Pipeline test+commit+push | ✅ |
| `test` | Validar schema/config | ✅ |
| `snapshot` | Guardar estado repo | ✅ |
| `maintenance` / `clean` | Mantenimiento disco | ✅ |
| `rotate` | Rotar logs | ✅ |
| `health` | Salud GX10 | ✅ |
| `snc` / `heartbeat` | Estado SNC | ✅ |
| `doctor` | Diagnóstico completo | ✅ |
| `metrics` | Métricas router | ✅ |
| `index` | Indexar documentos RAG | ✅ |
| `ask` | Consultar documentos | ✅ |
| `memory` | Estadísticas memoria RAG | ✅ |

### 4.2 API HTTP (FastAPI)

| Endpoint | Método | Descripción | Response |
|----------|--------|-------------|----------|
| `GET /health` | GET | Health check general | `{global, components[]}` |
| `GET /ready` | GET | Readiness de dependencias | `{ready, dependencies[]}` |
| `GET /metrics` | GET | Métricas Prometheus | `text/plain` OpenMetrics |

### 4.3 API de Plugin

| Clase/Módulo | Descripción | Status |
|-------------|-------------|--------|
| `PluginBase` (ABC) | Clase base para plugins | ✅ |
| `PluginManifest` | Validación de manifiesto YAML | ✅ |
| `PluginRegistry` (v1) | Registro de plugins legacy | ✅ |
| `RegistryV2` | Registro con scanning, events, degraded mode | ✅ |
| `HookManager` | Gestión de hooks (on_startup, etc.) | ✅ |
| `EventBus` | Publicación/suscripción de eventos | ✅ |

---

## 5. Puntos de Extensión

| Punto | Mecanismo | Documentación | Status |
|-------|-----------|---------------|--------|
| **Plugins** | `PluginBase.execute(context) → dict` vía `RegistryV2` | `docs/plugins/PLUGIN_API.md` | ✅ |
| **EventBus** | `EventBus.publish(topic, payload)` + suscripción | `ADR-011-02` | ✅ |
| **Hooks** | `HookManager.register_plugin_hooks()` (4 hooks) | `ADR-011-03` | ✅ |
| **Rerankers** | `BaseReranker.rerank(query, candidates)` | `motor/intelligence/reranking/` | ✅ |
| **Memory Stores** | `MemoryStore` ABC (store, get, search, delete, count) | `ADR-012-02` | ✅ |
| **Fact Extractors** | `FactExtractor.extract(episode)` | `motor/intelligence/memory/` | ✅ |
| **Compression Policies** | `CompressionPolicy` (should_run, select, delete) | `motor/intelligence/memory/` | ✅ |
| **Forgetting Policies** | `ForgettingPolicy` (should_forget) | `ADR-012-03` | ✅ |
| **Voting Strategies** | `VotingStrategy.aggregate(results)` | `ADR-013-01` | ✅ |
| **Reflection Strategies** | `ReflectionStrategy.reflect(result, iteration)` | `ADR-013-01` | ✅ |
| **Providers** (LLM) | `Provider` ABC (chat, health) | `core/mochila/providers/` | ✅ |
| **Notifiers** | `Notifier.send(notification)` | `knowledge/engine/notify.py` | ✅ |
| **Pipeline Stages** | 6 hooks: pre_ingest, post_ingest, pre_search, post_search, pre_index, post_index | `motor/pipeline/` | ✅ |

---

## 6. ADRs Relacionados (16 total)

| ADR | Título | Fase | Área |
|-----|--------|------|------|
| ADR-001 | NDJSON Audit | F0 | Auditoría |
| ADR-002 | Flock Compile Lock | F0 | Compilación |
| ADR-003 | Determinism ABI | F0 | Determinismo |
| ADR-004 | Async Archive | F1 | Archivado |
| ADR-005 | SQLite WAL | F2 | Persistencia |
| ADR-006 | Systemd Timer | F3 | Scheduling |
| ADR-007 | Core Modification Rule (Núcleo Congelado) | F7 | Gobernanza |
| ADR-011-01 | Plugin API Contract | F11 | Plugins |
| ADR-011-02 | EventBus Contract | F11 | Eventos |
| ADR-011-03 | Hooks System | F11 | Hooks |
| ADR-011-04 | Plugin Versioning | F11 | Versionado |
| ADR-012-01 | Quality Contract (KE) | F12 | Calidad |
| ADR-012-02 | Memory Model | F12 | Memoria |
| ADR-012-03 | Memory Lifecycle | F12 | Memoria |
| ADR-013-01 | Consensus Protocol | F13 | Consenso |
| ADR-013-02 | Deployment & Observability | F13 | Despliegue |

---

## 7. Estado por Subsistema

| Subsistema | Módulo | Tests | Cobertura | Estado |
|-----------|--------|-------|-----------|--------|
| **CLI** | `motor/cli/` | 4 | — | ✅ |
| **EventBus** | `motor/events/` | `test_event_bus.py`, `test_hook_manager.py` | — | ✅ |
| **Plugin System** | `motor/plugin/` | `test_plugin_*`, `test_registry_v2*` | — | ✅ |
| **Pipeline** | `motor/pipeline/` | `test_pipeline.py` | — | ✅ |
| **Retrieval** | `motor/intelligence/retrieval/` | `test_vector_*`, `test_hybrid*` | — | ✅ |
| **Reranking** | `motor/intelligence/reranking/` | `test_reranker*` | — | ✅ |
| **Memory** | `motor/intelligence/memory/` | `test_episodic*`, `test_semantic*`, `test_forgetting*`, `test_memory_compression*`, `test_extractor*` | — | ✅ |
| **Agents** | `motor/intelligence/agents/` | `test_agents.py` | — | ✅ |
| **Consensus** | `motor/intelligence/agents/consensus.py` | `test_voting.py` | — | ✅ |
| **Reflection** | `motor/intelligence/agents/reflection.py` | `test_reflection.py` | — | ✅ |
| **Parallel Executor** | `motor/intelligence/agents/parallel.py` | `test_parallel.py` | — | ✅ |
| **Observability** | `motor/observability/` | `test_observability*` | — | ✅ |
| **Knowledge Engine** | `knowledge/engine/` | `test_knowledge_engine.py` | — | Legacy (1.x) |
| **Mochila/Providers** | `core/mochila/` | `test_mochila.py` | — | Legacy |
| **Core Legacy** | `core/` | varios | — | En migración |

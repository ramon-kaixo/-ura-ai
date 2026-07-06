# API Inventory

> **Fecha:** 2026-07-06
> **Alcance:** Cierre transversal F10–F13
> **Nota:** Solo APIs públicas. Módulos internos de `core/` legacy excluidos (ver `TECHNICAL_DEBT.md` H02).

---

## 1. Clases Públicas (motor/)

### 1.1 Core

| Clase | Archivo | Tipo | Descripción |
|-------|---------|------|-------------|
| `UraConfig` | `motor/core/config.py` | Dataclass | Configuración central (14 campos) |
| `DegradedMode` | `motor/core/state.py` | Singleton | Degradación controlada de subsistemas |
| `BaseExecutor` | `motor/core/executor.py` | ABC | Ejecutor de comandos/subprocesos |
| `SubprocessExecutor` | `motor/core/executor.py` | Implementación | Ejecutor con subprocess.run |
| `ProcessResult` | `motor/core/executor.py` | Dataclass | Resultado de ejecución (returncode, stdout, stderr, duration) |
| `QdrantClient` | `motor/core/qdrant_client.py` | Clase | Cliente Qdrant con degradación y fallback |

### 1.2 Events

| Clase | Archivo | Tipo | Descripción |
|-------|---------|------|-------------|
| `EventBus` | `motor/events/bus.py` | Clase | Pub/sub tipado con hooks |
| `HookManager` | `motor/events/hooks.py` | Clase | Gestión de hooks con circuit breaker |
| `Event` | `motor/events/event.py` | Dataclass | Payload de evento tipado |
| `CompatEventBus` | `motor/events/compat.py` | Bridge | Adaptador legacy ↔ nuevo EventBus |

### 1.3 Pipeline

| Clase | Archivo | Tipo | Descripción |
|-------|---------|------|-------------|
| `PipelineDefinition` | `motor/pipeline/definition.py` | Clase | Definición YAML de pipeline |
| `PipelineOrchestrator` | `motor/pipeline/orchestrator.py` | Clase | Orquestador de etapas |
| `PipelineExecutor` | `motor/pipeline/executor.py` | Clase | Ejecutor con métricas |
| `PipelineLoader` | `motor/pipeline/loader.py` | Clase | Cargador de YAML |

### 1.4 Plugin System

| Clase | Archivo | Tipo | Descripción |
|-------|---------|------|-------------|
| `PluginBase` | `motor/plugin/base.py` | ABC | Clase base para plugins (abstract: `execute`) |
| `PluginManifest` | `motor/plugin/manifest.py` | Dataclass | Manifiesto de plugin (name, version, description, author) |
| `PluginRegistry` | `motor/plugin/registry.py` | Clase | Registro v1 (legacy) |
| `RegistryV2` | `motor/plugin/registry_v2.py` | Clase | Registro v2 con scanning, eventos, degraded mode |

### 1.5 Intelligence — Retrieval

| Clase | Archivo | Tipo | Descripción |
|-------|---------|------|-------------|
| `VectorRetriever` | `motor/intelligence/retrieval/vector.py` | Clase | Búsqueda vectorial sobre Qdrant |
| `LexicalRetriever` | `motor/intelligence/retrieval/lexical.py` | Clase | Búsqueda BM25/FTS5 |
| `HybridRetriever` | `motor/intelligence/retrieval/hybrid.py` | Clase | Fusión vectorial + léxico (RRF, score, dinámica) |
| `RetrievalPipeline` | `motor/intelligence/pipeline.py` | Clase | Pipeline completo retrieval+reranker+memory |

### 1.6 Intelligence — Reranking

| Clase | Archivo | Tipo | Descripción |
|-------|---------|------|-------------|
| `BaseReranker` | `motor/intelligence/reranking/reranker.py` | ABC | Reranker abstracto (abstract: `rerank`) |
| `BaseReranker` | `motor/intelligence/reranking/base.py` | ABC | ⚠️ DUPLICADO (misma firma) |
| `CrossEncoderReranker` | `motor/intelligence/reranking/ce.py` | Clase | Reranker con cross-encoder |
| `LLMReranker` | `motor/intelligence/reranking/llm.py` | Clase | Reranker con LLM (Ollama) |
| `NoOpReranker` | `motor/intelligence/reranking/noop.py` | Clase | Reranker identidad (passthrough) |

### 1.7 Intelligence — Memory

| Clase | Archivo | Tipo | Descripción |
|-------|---------|------|-------------|
| `MemoryStore` | `motor/intelligence/memory/base.py` | ABC | Almacén de memoria (abstract: store, get, search, delete, count) |
| `MemoryRecord` | `motor/intelligence/memory/record.py` | Dataclass | Registro de memoria (id, content, type, metadata, score) |
| `EpisodicMemory` | `motor/intelligence/memory/episodic.py` | Clase | Memoria episódica con SQLite persistente |
| `SemanticMemory` | `motor/intelligence/memory/semantic.py` | Clase | Memoria semántica con extracción de hechos |
| `FactExtractor` | `motor/intelligence/memory/extractor.py` | ABC | Extractor de hechos (abstract: `extract`) |
| `LLMFactExtractor` | `motor/intelligence/memory/extractor_llm.py` | Clase | Extractor vía Ollama |
| `EpisodeStoreConfig` | `motor/intelligence/memory/episodic.py` | Dataclass | Config: max_episodes, ttl, persist_path |
| `SemanticFact` | `motor/intelligence/memory/extractor.py` | Dataclass | Hecho semántico (subject, predicate, object, confidence) |
| `Episode` | `motor/intelligence/memory/record.py` | Dataclass | Episodio (agent, task, result, timestamp, metadata) |
| `CompressionPolicy` | `motor/intelligence/memory/compression.py` | ABC | Política de compresión (abstract: should_run, select_candidates) |
| `ForgettingPolicy` | `motor/intelligence/memory/forgetting.py` | ABC | Política de olvido (abstract: should_forget, name) |
| `MemoryOrchestrator` | `motor/intelligence/memory/orchestrator.py` | Clase | Orquestador del ciclo de vida (store→extract→consolidate) |
| `RetrievalAugmentedConfig` | `motor/intelligence/memory/retrieval.py` | Dataclass | Config de retrieval contextual |

### 1.8 Intelligence — Agents

| Clase | Archivo | Tipo | Descripción |
|-------|---------|------|-------------|
| `Agent` | `motor/intelligence/agents/base.py` | ABC | Agente base (abstract: `run`) |
| `AgentTask` | `motor/intelligence/agents/base.py` | Dataclass | Tarea de agente (id, goal, context, metadata) |
| `AgentResult` | `motor/intelligence/agents/base.py` | Dataclass | Resultado (agent_id, success, data, error, metadata) |
| `PlannerAgent` | `motor/intelligence/agents/planner.py` | Clase | Descompone tareas en subtareas |
| `ResearcherAgent` | `motor/intelligence/agents/researcher.py` | Clase | Consulta retrieval + memoria |
| `ExecutorAgent` | `motor/intelligence/agents/executor.py` | Clase | Ejecuta subtareas |
| `ValidatorAgent` | `motor/intelligence/agents/validator.py` | Clase | Valida resultados |
| `SupervisorAgent` | `motor/intelligence/agents/supervisor.py` | Clase | Coordina agentes |
| `MultiAgentRuntime` | `motor/intelligence/agents/runtime.py` | Clase | Runtime multi-agente |

### 1.9 Intelligence — Consensus

| Clase | Archivo | Tipo | Descripción |
|-------|---------|------|-------------|
| `VotingStrategy` | `motor/intelligence/agents/consensus.py` | ABC | Estrategia de votación (abstract: name, aggregate) |
| `ConsensusResult` | `motor/intelligence/agents/consensus.py` | Dataclass | Resultado (decision, confidence, votes, details) |
| `VotingEngine` | `motor/intelligence/agents/consensus.py` | Clase | Motor de votación multi-agente |
| `MajorityVoting` | `motor/intelligence/agents/consensus.py` | Clase | Voto por mayoría simple |
| `WeightedConsensus` | `motor/intelligence/agents/consensus.py` | Clase | Consenso ponderado por pesos |

### 1.10 Intelligence — Reflection

| Clase | Archivo | Tipo | Descripción |
|-------|---------|------|-------------|
| `ReflectionStrategy` | `motor/intelligence/agents/reflection.py` | ABC | Estrategia de reflexión (abstract: reflect) |
| `ReflectionDecision` | `motor/intelligence/agents/reflection.py` | Dataclass | Decisión (accept, revise, reject, confidence, feedback) |
| `ReflectionAgent` | `motor/intelligence/agents/reflection.py` | Clase | Agente de auto-reflexión con iteraciones |

### 1.11 Intelligence — Parallel Execution

| Clase | Archivo | Tipo | Descripción |
|-------|---------|------|-------------|
| `ParallelExecutor` | `motor/intelligence/agents/parallel.py` | Clase | Ejecutor paralelo con pool de workers |
| `ExecutionResult` | `motor/intelligence/agents/parallel.py` | Dataclass | Resultado (task_id, success, data, error, duration) |

### 1.12 Observability

| Clase | Archivo | Tipo | Descripción |
|-------|---------|------|-------------|
| `HealthRegistry` | `motor/observability/health.py` | Clase | Registro de salud (healthy/degraded/unhealthy) |
| `ReadinessRegistry` | `motor/observability/readiness.py` | Clase | Registro de readiness de dependencias |
| `MetricsRegistry` | `motor/observability/metrics.py` | Clase | Contenedor de métricas (Counter, Gauge, Histogram, Timer) |
| `Counter` | `motor/observability/metrics.py` | Clase | Contador thread-safe con labels |
| `Gauge` | `motor/observability/metrics.py` | Clase | Gauge thread-safe con labels |
| `Histogram` | `motor/observability/metrics.py` | Clase | Histograma thread-safe con buckets |
| `Timer` | `motor/observability/metrics.py` | Clase | Timer con context manager |
| `Instrumentation` | `motor/observability/instrumentation.py` | Clase | Wrapper de instrumentación |
| `JSONFormatter` | `motor/observability/logging.py` | Clase | Formateador JSON de logs |
| `ContextFilter` | `motor/observability/logging.py` | Clase | Filtro de contexto (correlation_id, workflow_id) |

### 1.13 Guard

| Clase | Archivo | Tipo | Descripción |
|-------|---------|------|-------------|
| `PreflightCheck` | `motor/guard/preflight.py` | Clase | Check pre-vuelo (schema, config, estado) |
| `SchemaVerifier` | `motor/guard/verifier.py` | Clase | Verificador de esquemas |

### 1.14 Scanner

| Clase | Archivo | Tipo | Descripción |
|-------|---------|------|-------------|
| `DiffDetector` | `motor/scanner/diff_detector.py` | Clase | Detector de diferencias en sistema |
| `SlidingWindow` | `motor/scanner/sliding_window.py` | Clase | Ventana deslizante para detección de anomalías |
| `Calibration` | `motor/scanner/calibration.py` | Clase | Calibración de baseline |

---

## 2. Abstract Base Classes (ABCs) — 12 únicos

| ABC | Archivo | Métodos Abstractos | Implementaciones Conocidas |
|-----|---------|-------------------|---------------------------|
| `BaseExecutor` | `motor/core/executor.py` | `run`, `arun` | `SubprocessExecutor` |
| `PluginBase` | `motor/plugin/base.py` | `execute(context)` | (a través de RegistryV2) |
| `Agent` | `motor/intelligence/agents/base.py` | `run(task)` | Planner, Researcher, Executor, Validator, Supervisor |
| `VotingStrategy` | `motor/intelligence/agents/consensus.py` | `name`, `aggregate` | `MajorityVoting`, `WeightedConsensus` |
| `ReflectionStrategy` | `motor/intelligence/agents/reflection.py` | `reflect` | `ReflectionAgent` |
| `BaseReranker` | `motor/intelligence/reranking/` | `rerank` | CrossEncoder, LLMReranker, NoOpReranker |
| `MemoryStore` | `motor/intelligence/memory/base.py` | `store`, `get`, `search`, `delete`, `count` | EpisodicMemory, SemanticMemory |
| `FactExtractor` | `motor/intelligence/memory/extractor.py` | `extract` | LLMFactExtractor |
| `CompressionPolicy` | `motor/intelligence/memory/compression.py` | `should_run`, `select_candidates`, `delete_originals` | — |
| `ForgettingPolicy` | `motor/intelligence/memory/forgetting.py` | `name`, `should_forget` | — |
| `Provider` | `core/mochila/providers/base.py` | `nombre`, `timeout`, `chat`, `health` | Ollama, Gemini, Groq, DeepSeek, OpenRouter |
| `Agent` (KE) | `knowledge/engine/agent.py` | `agent_id`, `execute(goal)` | — |

---

## 3. Protocol Classes — 13

| Protocol | Archivo | Métodos | Uso |
|----------|---------|---------|-----|
| `Clasificador` | `core/mochila/router.py` | `clasificar` | Clasificación de mensajes |
| `GovernanceStore` | `knowledge/engine/governance_store.py` | 4 métodos | Políticas de acceso |
| `Rule` | `knowledge/engine/rules.py` | `evaluate` | Evaluación de reglas |
| `MemoryStore` | `knowledge/engine/memory_store.py` | 7 métodos | Almacén de memoria legacy |
| `Embedder` | `knowledge/engine/vector_base.py` | 4 métodos | Embeddings |
| `VectorStore` | `knowledge/engine/vector_base.py` | 6 métodos | Búsqueda vectorial |
| `KnowledgeRepository` | `knowledge/engine/repository.py` | 5 métodos | Repositorio de conocimiento |
| `GraphRetriever` | `knowledge/engine/graphrag.py` | 6 métodos | Retrieval sobre grafo |
| `AssetStore` | `knowledge/engine/asset_store.py` | 7 métodos | Almacén de activos |
| `LineageStore` | `knowledge/engine/lineage_store.py` | 4 métodos | Trazabilidad |
| `AuditBackend` | `knowledge/engine/audit/backend.py` | 3 métodos | Backend de auditoría |
| `Extractor` | `knowledge/engine/extractors/base.py` | `extract` | Extracción de documentos |
| `Notifier` | `knowledge/engine/notify.py` | `send` | Notificaciones |

---

## 4. Event Topics (13)

| Constante | Valor | Publicadores | Suscriptores |
|-----------|-------|-------------|--------------|
| `SYSTEM_STARTED` | `system.started` | `main()` | `HookManager.on_startup` |
| `SYSTEM_SHUTDOWN` | `system.shutdown` | `main()` | `HookManager.on_shutdown` |
| `SYSTEM_DEGRADED` | `system.degraded` | `DegradedMode` | `Instrumentation.instrument_eventbus` |
| `SYSTEM_RESTORED` | `system.restored` | `DegradedMode` | — |
| `PIPELINE_STARTED` | `pipeline.started` | `PipelineExecutor` | — |
| `PIPELINE_COMPLETED` | `pipeline.completed` | `PipelineExecutor` | — |
| `PIPELINE_FAILED` | `pipeline.failed` | `PipelineExecutor` | — |
| `PLUGIN_LOADED` | `plugin.loaded` | `RegistryV2` | — |
| `PLUGIN_UNLOADED` | `plugin.unloaded` | `RegistryV2` | — |
| `PLUGIN_ERROR` | `plugin.error` | `RegistryV2` | — |
| `EXECUTOR_STARTED` | `executor.started` | `SubprocessExecutor` | — |
| `EXECUTOR_COMPLETED` | `executor.completed` | `SubprocessExecutor` | — |
| `CONFIG_CHANGED` | `config.changed` | `UraConfig` | — |

---

## 5. Puntos de Extensión (Plugins)

| Punto | Clase Base | Método | Registro | Documentación |
|-------|-----------|--------|----------|---------------|
| Plugin | `PluginBase` | `execute(context) → dict` | `RegistryV2.scan()` + `register()` | `docs/plugins/PLUGIN_API.md` |
| Hook | `HookManager` | `register_plugin_hooks(hooks)` | `HookManager` | `ADR-011-03` |
| Event | `EventBus` | `publish(topic, payload)` | `EventBus.subscribe(topic, handler)` | `ADR-011-02` |
| Pipeline Stage | `PipelineExecutor` | 6 hooks pre/post | PipelineDefinition YAML | `motor/pipeline/` |

---

## 6. Componentes Experimentales

| Componente | Archivo | Razón | Estado |
|-----------|---------|-------|--------|
| `LLMReranker` | `motor/intelligence/reranking/llm.py` | Sin benchmark de calidad | ⚠️ Experimental |
| `LLMFactExtractor` | `motor/intelligence/memory/extractor_llm.py` | Sin benchmark de calidad | ⚠️ Experimental |
| `MemoryOrchestrator` | `motor/intelligence/memory/orchestrator.py` | Sin scheduler automático | ⚠️ Sin activar |
| `ReflectionAgent` | `motor/intelligence/agents/reflection.py` | No integrado en runtime | ⚠️ Independiente |

---

## 7. Resumen

| Categoría | Cantidad | 
|-----------|----------|
| Clases públicas (motor/) | ~60 |
| ABCs únicos | 12 |
| Protocol classes | 13 |
| Event topics | 13 |
| Puntos de extensión | 4 |
| Componentes experimentales | 4 |
| Plugins registrados | 0 (sistema listo, sin plugins creados) |

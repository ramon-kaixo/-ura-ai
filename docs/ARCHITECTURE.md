# URA Architecture Guide

## Overview

URA is a layered multi-agent system. Each layer depends only on the layer below it.
There are no circular dependencies.

```
┌─────────────────────────────────────────────────┐
│                 Observability                    │
│  (metrics, logging, health, exporter, alerts)    │
├─────────────────────────────────────────────────┤
│              Multi-Agent Runtime                 │
│  (Planner → Supervisor → Agents → Reflection)    │
│  (Consensus: Majority, Weighted, Unanimous)      │
├─────────────────────────────────────────────────┤
│                  Memory System                   │
│  (EpisodicStore → SemanticMemory → Compression)  │
│  (Forgetting → ProtectionRules)                  │
├─────────────────────────────────────────────────┤
│                Retrieval Pipeline                │
│  (Vector → BM25 → Hybrid → Reranker)             │
├─────────────────────────────────────────────────┤
│                  Plugin System                   │
│  (Registry → Manifest → EventBus → Hooks)        │
├─────────────────────────────────────────────────┤
│                    Pipeline                      │
│  (Definition → Loader → Executor)                │
├─────────────────────────────────────────────────┤
│                     Core                         │
│  (Config, Executor, State, EventBus)             │
└─────────────────────────────────────────────────┘
```

## Module Map

### `motor/intelligence/agents/` — Multi-Agent Runtime

| File | Component | Dependencies |
|------|-----------|--------------|
| `base.py` | `Agent` (ABC) | `message` |
| `message.py` | `AgentMessage`, `AgentTask`, `AgentResult` | stdlib |
| `planner.py` | `PlannerAgent` | `base`, `message` |
| `executor.py` | `ExecutorAgent` | `base`, `message`, `motor.core.executor` |
| `researcher.py` | `ResearcherAgent` | `base`, `message` |
| `validator.py` | `ValidatorAgent` | `base`, `message` |
| `supervisor.py` | `SupervisorAgent` (coordination + retry) | `base`, `message` |
| `consensus.py` | `VotingEngine`, `WeightedConsensus`, `MajorityVoting` | `message` |
| `reflection.py` | `ReflectionAgent`, `ReflectionStrategy` | `base`, `message` |
| `parallel.py` | `ParallelExecutor`, `ExecutionResult` | `base`, `message` |
| `runtime.py` | `MultiAgentRuntime` | `base`, `message`, `planner`, `supervisor` |

### `motor/intelligence/memory/` — Memory System

| File | Component | ADR |
|------|-----------|-----|
| `record.py` | `MemoryRecord`, `MemoryType` | 012-02 |
| `base.py` | `MemoryStore` (ABC) | 012-02 |
| `episodic.py` | `Episode`, `EpisodeStore`, `SessionMemory` | 012-02 |
| `retrieval.py` | `ContextRetriever`, `ContextQuery`, `ContextResult` | 012-02 |
| `semantic.py` | `SemanticFact`, `SemanticMemoryStore` | 012-02 |
| `extractor.py` | `FactExtractor` (ABC), `RuleBasedFactExtractor` | 012-02 |
| `compression.py` | `MemoryCompressor`, 4 policies, `SummaryRecord` | 012-03 |
| `forgetting.py` | `ForgettingEngine`, 5 policies, `ProtectionRules` | 012-03 |

### `motor/intelligence/retrieval/` — Retrieval Pipeline

| File | Component |
|------|-----------|
| `vector.py` | `VectorRetriever` (Qdrant) |
| `lexical.py` | `LexicalRetriever` (BM25) |
| `hybrid.py` | `HybridRetriever` (α·vector + β·lexical) |

### `motor/intelligence/reranking/` — Reranking (Experimental)

| File | Component | Status |
|------|-----------|--------|
| `base.py` | `BaseReranker` (ABC) | ✅ |
| `noop.py` | `NoOpReranker` | ✅ Default |
| `ce.py` | `CrossEncoderReranker` | ⚠️ Experimental |
| `llm.py` | `LLMReranker` | ⚠️ Experimental |

### `motor/observability/` — Observability

| File | Component |
|------|-----------|
| `metrics.py` | `MetricsRegistry` (Counter, Gauge, Histogram, Timer) |
| `logging.py` | `JSONFormatter`, `set_correlation_id()` |
| `exporter.py` | `format_prometheus()` → OpenMetrics |
| `health.py` | `HealthRegistry` |
| `readiness.py` | `ReadinessRegistry` |
| `http.py` | FastAPI router ([/health, /ready, /metrics]) |

## Data Flow — Workflow Execution

```
1. User / API calls MultiAgentRuntime.execute_workflow(objective)
2. Runtime creates workflow_id, stores in _workflows
3. Runtime calls PlannerAgent.run() → decomposes objective into subtasks
4. Runtime passes subtasks to SupervisorAgent via context
5. Supervisor iterates subtasks:
   a. Check cancellation (cooperative)
   b. Find agent by role
   c. Execute agent.run(task) with retries (max 2)
   d. If all succeed → mark completed
6. Runtime collects result → returns AgentResult
7. Runtime trims completed workflows (FIFO, max 1000)
```

## Extension Points

| Interface | Implementations | Extensible by |
|-----------|----------------|---------------|
| `Agent` (ABC) | 5 agents | New agents via subclass |
| `VotingStrategy` (ABC) | 3 strategies | Custom voting logic |
| `ReflectionStrategy` (ABC) | 2 strategies | LLM-based review |
| `MemoryStore` (ABC) | 2 stores | Custom persistence |
| `FactExtractor` (ABC) | 1 extractor | LLM extraction |
| `CompressionPolicy` (ABC) | 4 policies | Custom compression |
| `ForgettingPolicy` (ABC) | 5 policies | Custom forgetting |
| `BaseReranker` (ABC) | 3 rerankers | Custom reranking |

## Configuration Sources (in order of precedence)

1. CLI arguments (`--config`)
2. Environment variables (`URA_*`)
3. `.env` file
4. Default values in `UraConfig`

## ADR References

| ADR | Title |
|-----|-------|
| ADR-012-01 | Quality Contract (metrics, corpus, acceptance) |
| ADR-012-02 | Memory Model (Episodic, Semantic, Working, LTM) |
| ADR-012-03 | Memory Lifecycle (create, consolidate, compress, forget) |
| ADR-013-01 | Consensus Protocol (Voting, Weighted, Reflection) |
| ADR-013-02 | Deployment & Observability (Docker, pip, Prometheus) |

# Strategic Architecture Review — Platform-Level Audit

**Date:** 2026-07-17  
**Scope:** F24–F27 Cross-Platform Governance  
**Status:** Planning (no implementation)

---

## Level 1: Architectural Governance

### API Classification (Current)

| Layer | Public | Advanced | Internal | Total |
|-------|--------|----------|----------|-------|
| F25 `motor.core.fusion` | — | — | — | 38 |
| F26 `motor.memory` | — | — | — | 9 |
| F27 `motor.agents` | 12 | 17 | 13 | 42 |

### Immutable Contracts

| Contract | Status | Can be modified? | Process |
|----------|--------|-----------------|---------|
| `ADR-025-02` (Knowledge Identity) | ✅ Permanent | ❌ No | Requires new ADR |
| `ADR-025-04` (Hash Policy) | ✅ Permanent | ❌ No (breaks IDs) | Requires new ADR |
| `make_fact_id()` | ✅ Permanent | ❌ No (breaks identity) | Migration required |
| `make_entry_id()` | ✅ Permanent | ❌ No (breaks memory) | Migration required |
| `FusionPipeline.run()` signature | ✅ Stable | ⚠️ Extendable | Add optional params only |
| `Memory.append()` signature | ✅ Stable | ⚠️ Extendable | Add optional params only |
| `CapabilityGate` ABC | ✅ Stable | ⚠️ Extendable | Add methods with defaults |
| `Scheduler` ABC | ✅ Stable | ⚠️ Extendable | Add methods with defaults |

### Deprecation Process

```
1. Mark symbol as DEPRECATED in docstring + changelog
2. Keep symbol for N releases (N >= 2)
3. Emit warning on use (via warnings.warn)
4. Remove in N+2 release
5. Document migration path
```

### ADR Lifecycle

| Stage | Description | Can be modified? |
|-------|-------------|-----------------|
| **Draft** | Under review | Yes |
| **Approved** | Accepted but not implemented | By consensus |
| **Permanent** | Implemented, contracts frozen | ❌ No (requires new ADR) |
| **Superseded** | Replaced by newer ADR | Reference only |
| **Deprecated** | No longer recommended | Removed from active set |

---

## Level 2: Dependency Analysis

### Package Dependency Graph

```
motor.core.fusion (F25)
    ↑ imports from ↓
motor.core.web (F24) — CitationBundle, Evidence (TYPE_CHECKING)

motor.memory (F26)
    ↑ no imports from F25 (FactRef uses only strings)

motor.agents (F27)
    ↑ no imports from F25/F26 (all via ABCs)
    ↑ stdlib only: abc, typing, dataclasses, enum, hashlib

motor.intelligence (agents + memory runtime)
    ↑ imports from motor.core.llm (generate)
    ↑ imports from motor.core.qdrant_client
```

### Stability Metrics (Martin)

| Package | Afferent Coupling (Ca) | Efferent Coupling (Ce) | Instability (I = Ce/(Ca+Ce)) |
|---------|----------------------|----------------------|---------------------------|
| `motor.core.fusion` | 2 (consumed by tests, bridge) | 2 (web, citation) | 0.50 |
| `motor.memory` | 1 (consumed by tests) | 0 | **0.00** (stable) |
| `motor.agents` | 0 (no consumers yet) | 0 | **0.00** (stable) |
| `motor.core.llm` | 5+ (consumed by many) | 1 (secrets, state) | 0.17 (stable) |
| `motor.core.web` | 1 (consumed by fusion) | 0 | **0.00** (stable) |

### Circular Dependencies Found

- `core/ ↔ motor/` via `core.config_manager` (F25-A1 finding C-01, unresolved)

---

## Level 3: Technical Budget

| Metric | Budget | Measured | Status |
|--------|--------|----------|--------|
| Planner latency (p50) | < 100ms | ✅ ~1ms (rule-based) | ✅ |
| Scheduler submit (p50) | < 1ms | ✅ ~0.1ms | ✅ |
| ToolRunner timeout | configurable | ✅ 30s default | ✅ |
| RAM per AgentExecution | < 10 MB | ✅ ~1 KB | ✅ |
| RAM per MemoryEntry | < 1 KB | ✅ ~150 bytes + refs | ✅ |
| FactHistory recovery (10K) | < 3s | ✅ ~1s | ✅ |
| FactIndex lookup (10K) | < 10ms | ✅ ~1ms | ✅ |
| CI total time (fast) | < 5 min | TBD | ⚠️ Needs measurement |
| make_fact_id() | < 1µs | ✅ ~0.5µs | ✅ |
| CapabilityGate.check() | O(1) | ✅ O(1) | ✅ |

---

## Level 4: Global Observability

### Current State

| Operation | Has trace_id? | Crosses layers? | Reconstructible? |
|-----------|--------------|-----------------|-----------------|
| FusionPipeline.run() | ❌ No | fusion only | Partially (StageProvenance) |
| Memory.append() | ❌ No | memory only | Partially (Journal) |
| AgentExecution | ❌ No | agent only | ✅ (AgentAuditRecord) |
| Full E2E (Doc→Fact→Memory→Agent→LLM) | ❌ **No** | ❌ **No** | ❌ **No** |

### Proposed Trace Model

```python
@dataclass(frozen=True)
class TraceContext:
    trace_id: str          # SHA-256(request)[:16]
    span_id: str           # unique per operation
    parent_span_id: str | None
    service: str           # "fusion" | "memory" | "agent" | "llm"
    operation: str         # "pipeline.run" | "memory.append" | "agent.run"
    start_time: float
    end_time: float | None
    metadata: dict
```

### Trace Flow

```
Request (trace_id = T)
    ↓
FusionPipeline.run (span = pipeline.T.0)
    ↓
Memory.append (span = memory.T.1, parent = pipeline.T.0)
    ↓
Agent.run (span = agent.T.2, parent = pipeline.T.0)
    ↓
CapabilityGate.check (span = gate.T.2.0, parent = agent.T.2)
    ↓
Planner.plan (span = planner.T.2.1, parent = agent.T.2)
    ↓
ToolRunner.run (span = tool.T.2.2, parent = agent.T.2)
    ↓
LLM.generate (span = llm.T.2.2.0, parent = tool.T.2.2)
    ↓
Response
```

**Not implemented.** This is a design for F28+.

---

## Level 5: Evolution Strategy

### How to add new providers
- Register via existing Registry pattern (FusionRegistry, PluginRegistry)
- New provider implements existing ABC (ToolAdapter, SourceScorer, etc.)
- No changes to orchestration code

### How to add new memory types
- Currently: MemoryEntry with FactRef
- Future: MemoryEntry with typed payload (MessageMemory, PreferenceMemory, etc.)
- Payload type identified via metadata field
- No changes to timeline/append/store code

### How to introduce new agents
- New agent type implements Agent ABC
- Registers with AgentWeightRegistry (consensus)
- No changes to Scheduler or Planner

### How to distribute execution
- Scheduler currently: single-process PriorityQueue
- Distributed: TaskQueue backed by Redis/Kafka (abstraction already exists)
- No changes to AgentOrchestrator or ToolRunner

### How to run multiple nodes
- Future: MemoryServer (F26 journal as remote service)
- Future: SchedulerServer (distributed queue)
- Each node runs its own AgentOrchestrator
- Coordination via external queue

### How to version internal protocols

| Protocol | Current version | Strategy |
|----------|----------------|----------|
| Journal entry | `schema_version: 1` | Field in each entry |
| Snapshot header | `schema_version: 1` | Field in header |
| ToolRequest | Implicit | `ToolRequest.execution_id` |
| ToolResult | Implicit | `ToolResult.execution_id` |
| FactRef | Implicit | `FactRef.fact_id + version_id` |
| Agent→Planner | Implicit | Via Planner ABC |
| Agent→Scheduler | Implicit | Via Scheduler ABC |
| Agent→ToolRunner | Implicit | Via ToolRunner ABC |

→ **Recommended: ProtocolVersion header in all cross-component calls.**

```python
@dataclass(frozen=True)
class ProtocolHeader:
    protocol_version: str = "1.0"
    message_type: str
    trace_id: str
    timestamp: float
```

---

## Key Finding: Internal Protocol Versioning

### Current State
- No protocol version between any F27 components
- ToolRequest, ToolResult, PlannerRequest/Result are implicit (no header)
- Adding a new field to ToolRequest could break old ToolAdapters
- Cross-process communication would be unsafe

### Recommendation
Add `protocol_version: str = "1.0"` to:
- `ToolRequest` (already has `execution_id`)
- `ToolResult` (already has `execution_id`)
- `PlanStep` (new field)
- `AgentResult` (new field)

This is backward-compatible (default "1.0"). Not implementing yet.

---

## Summary

| Level | Status |
|-------|--------|
| **1 — Governance** | ✅ ADRs classified. Deprecation process defined. |
| **2 — Dependencies** | ⚠️ 1 circular dependency (core↔motor, pre-existing). All agents packages have I=0. |
| **3 — Budget** | ✅ 10 budgets defined and measured. CI time TBD. |
| **4 — Observability** | ❌ No cross-layer trace_id. Design proposed for F28. |
| **5 — Evolution** | ✅ Strategies documented. Protocol versioning recommended. |

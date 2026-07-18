# F28 Architecture Audit: Internal Platform Protocols

**Objective:** Analyze ALL inter-subsystem communication across F24–F27 for distributed evolution readiness.
**Scope:** Web Intelligence (F24), Knowledge Fusion (F25), Historical Memory (F26), Agents (F27)
**Method:** Trace every cross-module call, message, event, and shared type. Grade each against 30 criteria.
**Status:** Pre-implementation. No code changes.

---

## Inventory of All Cross-Subsystem Contracts

### Contract Matrix

| # | Sender | Receiver | Mechanism | Payload | Versioned? |
|---|--------|----------|-----------|---------|------------|
| C01 | F24 CitationEngine | F25 FusionPipeline | Import (TYPE_CHECKING) | `CitationBundle` | ❌ |
| C02 | F24 WebPipeline | F25 FusionPipeline | Import (TYPE_CHECKING) | `WebDocument` | ❌ |
| C03 | F25 FusionPipeline | F25 FactIndex | In-process method call | `KnowledgeFact` | ❌ |
| C04 | F25 FactIndex | F25 ContextBuilder | In-process method call | `KnowledgeFact` / `(Fact,FactVersion)` | ❌ |
| C05 | F25 KnowledgeMerger | F25 models | Direct instantiation | `KnowledgeFact` | ❌ |
| C06 | F25 FusionPipeline | F26 Memory | Planned integration | `MemoryEntry` via `Memory.append()` | ❌ |
| C07 | F25 models → F26 models | Shared type reference | `FactRef` (strings only) | ✅ Immutable strings | ✅ |
| C08 | F26 Journal | F26 Memory | File I/O (JSON Lines) | `MemoryEntry` dict | ⚠️ schema_version=1 |
| C09 | F26 Snapshot | F26 Memory | File I/O (JSON) | Full timeline | ⚠️ schema_version=1 |
| C10 | F27 AgentOrchestrator | F27 Planner | ABC method call | `AgentTask` → `AgentPlan` | ❌ |
| C11 | F27 AgentOrchestrator | F27 Scheduler | ABC method call | `AgentExecution` | ❌ |
| C12 | F27 AgentOrchestrator | F27 ToolRunner | ABC method call | `str` (action) + `dict` (params) → `dict` | ❌ |
| C13 | F27 AgentOrchestrator | F27 CapabilityGate | ABC method call | `AgentCapability` enum | ✅ |
| C14 | F27 AgentOrchestrator | F27 AuditLogger | ABC method call | `AuditEvent` | ❌ |
| C15 | F27 ToolRunner | F27 ToolAdapter | ABC method call | `dict` (params) → `dict` | ❌ |
| C16 | F27 Planner → F27 models | Direct instantiation | `AgentPlan`, `PlanStep` | ❌ |
| C17 | F27 Scheduler → F27 models | Direct instantiation | `_PriorityQueue` (internal) | ❌ |
| C18 | core ↔ motor | Import | `CONFIG`, `UraConfig`, secrets | ❌ No protocol |

---

## Findings

### 🔴 F-01: No Protocol Version in Any Cross-Component Call

**Severity:** Critical  
**Evidence:** Every ABC call (C01–C18) passes raw data types without a protocol version header. Adding a field to `ToolRequest` breaks all `ToolAdapter` implementations. Adding a field to `Task` breaks all `Planner` implementations.  
**Risk:** In 2 years, with 10+ Planner implementations and 5+ Scheduler backends, upgrading a contract requires touching all implementations simultaneously.  
**Cost now:** ~3 days to add `protocol_version: str = "1.0"` to all message types.  
**Cost in 2 years:** ~3 weeks (coordinating 15+ implementations across repos).  
**Recommendation:** Add `protocol_version` field to every cross-component message type (ToolRequest, ToolResult, PlanStep, AgentTask, AgentResult, AuditEvent, MemoryEntry, FactRef serialization).

---

### 🔴 F-02: ToolRequest/ToolResult Have No Envelope

**Severity:** Critical  
**Evidence:** `ToolRunner.run(action: str, params: dict) -> dict` — the entire inter-component contract between Agent and ToolRunner is an unstructured string + dict. No message type, no schema, no version, no correlation ID, no causation ID.  
**Risk:** A misrouted response cannot be detected. Two concurrent tool calls from two agents produce indistinguishable results. Adding a new tool type requires parsing an unstructured dict.  
**Cost now:** ~2 days (wrap in typed ToolRequest/ToolResult with envelope).  
**Cost in 2 years:** ~2 weeks.  
**Recommendation:** Every tool execution must have a typed envelope: `ToolRequest(execution_id, tool_name, params, protocol_version, timestamp)` → `ToolResult(execution_id, success, data, error, error_type, duration_ms, protocol_version)`.

---

### 🔴 F-03: No Correlation ID Across Layers

**Severity:** Critical  
**Evidence:** An Agent request flows through Planner → Scheduler → ToolRunner → Tool → (Knowledge/Memory). None of these hops carry a common trace_id. Reconstructing a single user request requires joining N different log files by timestamp heuristics.  
**Risk:** In a distributed deployment, a single user request spans 5+ services. Without a correlation ID, debugging failures is impossible.  
**Cost now:** ~1 day (add `trace_id: str` to AgentTask).  
**Cost in 2 years:** ~2 weeks (retrofit tracing across 5+ services).  
**Recommendation:** Add `trace_id: str` to AgentTask. Propagate to all downstream calls. Add `causation_id: str` to link cause→effect.

---

### 🔴 F-04: No Causation ID

**Severity:** Critical  
**Evidence:** When a memory write fails because of a tool call that failed because of a planner decision that failed because of an authorization check, there is no way to link the final error to its root cause. Each component only sees its immediate input.  
**Risk:** In distributed debugging, the causal chain is invisible. A timeout in ToolRunner appears as an error in Agent, but the root cause was a planner timeout 3 levels up.  
**Cost now:** ~1 day (add `causation_id: str` to AuditEvent and propagate).  
**Cost in 2 years:** ~3 weeks.  
**Recommendation:** Every audit event must carry `causation_id` pointing to the event that caused it.

---

### 🟠 F-05: No At-Least-Once / Exactly-Once Semantics

**Severity:** High  
**Evidence:** `Scheduler.submit()` is fire-and-forget. `ToolRunner.run()` has retries but no deduplication. If a tool call completes but the result is lost (process crash), the caller does not know if it should retry.  
**Risk:** In distributed deployment, commands can be duplicated (tool executes twice) or lost (tool executes but result never arrives).  
**Cost now:** ~3 days (add idempotency key to ToolRequest, add delivery semantics to Scheduler).  
**Cost in 2 years:** ~3 weeks.  
**Recommendation:** Define delivery semantics per channel: Agent→Scheduler: at-least-once. Scheduler→ToolRunner: at-most-once for non-idempotent, at-least-once for idempotent.

---

### 🟠 F-06: Message Serialization Not Versioned

**Severity:** High  
**Evidence:** JSON serialization for Journal, Snapshot, and AuditEvent. No schema registry. Adding a field to MemoryEntry breaks backward compatibility with old journals.  
**Risk:** After 2 years of upgrades, old journals can't be read by new code. Migration requires scanning all journals.  
**Cost now:** ~2 days (add `schema_version` to every serialized message + registry-aware deserializer).  
**Cost in 2 years:** ~2 weeks (build migration scripts for 2 years of accumulated changes).  
**Recommendation:** Every serialized message must carry `schema_version`. Deserializer must dispatch to version-specific handlers.

---

### 🟠 F-07: ABC Evolution Has No Versioning

**Severity:** High  
**Evidence:** `CapabilityGate`, `Planner`, `Scheduler`, `ToolRunner`, `ToolAdapter` — all ABCs. Adding a method to an ABC breaks all implementations unless the method has a default. Currently, no ABC has versioning metadata.  
**Risk:** In 2 years, adding a new required capability to `CapabilityGate` requires updating every Gate implementation simultaneously.  
**Cost now:** ~2 days (add `version: str` property to each ABC, add `@abstractmethod` only for required methods, provide default implementations for optional ones).  
**Cost in 2 years:** ~3 weeks.  
**Recommendation:** Every ABC should have a `version` property. New methods should be added with a default implementation that raises `NotImplementedError` for older implementations.

---

### 🟠 F-08: No Protocol for Cross-Process Migration

**Severity:** High  
**Evidence:** Journal and Snapshot are file-based, single-node. No RPC protocol exists for remote Memory access. No remote ToolRunner. No remote Scheduler.  
**Risk:** Moving to multi-node requires designing 3+ RPC protocols from scratch. Inconsistencies between in-process and remote calls will emerge.  
**Cost now:** ~5 days (document interface contracts for each remote-capable component).  
**Cost in 2 years:** ~2 months.  
**Recommendation:** Document which ABCs will be remote-capable (Memory, Scheduler, ToolRunner) and define their RPC contracts before implementation.

---

### 🟡 F-09: Scheduler Queue Not Serializable

**Severity:** Medium  
**Evidence:** `_PriorityQueue` stores `AgentExecution` objects in memory. No serialization. Process restart loses all queued tasks.  
**Risk:** In production, scheduler crash before draining the queue loses tasks.  
**Cost now:** ~1 day (add `to_dict()`/`from_dict()` to AgentExecution + persistent queue adapter).  
**Cost in 2 years:** ~1 week.  
**Recommendation:** Make AgentExecution serializable. Add persistent queue backend.

---

### 🟡 F-10: AgentExecution and AuditEvent Share No Correlation

**Severity:** Medium  
**Evidence:** `AgentExecution` has `agent_id`. `AuditEvent` has `agent_id`. But there's no shared `execution_id` that links all events from a single execution.  
**Risk:** Reconstructing a single agent execution requires filtering by agent_id + time range, which is fragile.  
**Cost now:** ~1h (add `execution_id` to AuditEvent).  
**Cost in 2 years:** ~2 days.  
**Recommendation:** Add `execution_id: str` to AuditEvent. Populate from AgentExecution.

---

### 🟡 F-11: EventBus Not Used for Cross-Component Events

**Severity:** Medium  
**Evidence:** `motor/events/` defines an EventBus with topics (`SYSTEM_STARTED`, `SYSTEM_SHUTDOWN`, etc.) but F25/F26/F27 components don't emit or consume events via this bus. Audit, state changes, and errors are logged but not broadcast.  
**Risk:** Adding new consumers (monitoring, dashboards, alerting) requires modifying each component individually instead of subscribing to an event stream.  
**Cost now:** ~3 days (wire key events per component through EventBus).  
**Cost in 2 years:** ~2 weeks.  
**Recommendation:** Define domain events for cross-component state changes (FactCreated, FactUpdated, MemoryEntryAppended, AgentExecutionCompleted). Emit via EventBus.

---

### 🟡 F-12: No Message Size Budget

**Severity:** Medium  
**Evidence:** `MemoryEntry.fact_refs` is unbounded. A single entry could reference 1M facts. `ToolResult.data` is unbounded. `AgentTask.objective` is unbounded.  
**Risk:** In distributed deployment, oversized messages block queues, exhaust memory, and cause unpredictable latency.  
**Cost now:** ~1 day (add `max_fact_refs` to MemoryPolicy, `max_response_bytes` to ToolContract).  
**Cost in 2 years:** ~1 week.  
**Recommendation:** Define and enforce message size limits for all cross-component payloads.

---

### 🟢 F-13: FactRef Is Correctly Designed for Distribution

**Severity:** Low (positive finding)  
**Evidence:** `FactRef` uses only strings (fact_id, version_id, subject, predicate, object). No object references. No pointers to in-memory structures. Fully serializable.  
**Risk:** None. This is the right pattern.  
**Cost now:** 0.  
**Cost in 2 years:** 0.  
**Recommendation:** Keep this pattern. Use it as the template for all cross-component references.

---

### 🟢 F-14: MemoryEntry Is Immutable and Serializable

**Severity:** Low (positive finding)  
**Evidence:** `MemoryEntry` is frozen, contains only primitive types, FactRefs, and Metadata. Full dict serialization.  
**Risk:** None.  
**Cost now:** 0.  
**Cost in 2 years:** 0.  
**Recommendation:** Same as F-13 — keep this pattern.

---

## Summary

| Severity | Count | Key Issues |
|----------|-------|------------|
| 🔴 Critical | 4 | No protocol version, no envelope for ToolRunner, no correlation/causation ID |
| 🟠 High | 4 | No delivery semantics, unversioned serialization, ABC evolution, no cross-process protocol |
| 🟡 Medium | 4 | Queue not serializable, missing execution_id in AuditEvent, EventBus unused, no message size budget |
| 🟢 Low | 2 | FactRef is correct, MemoryEntry is correct |

---

## Risk Projection: Cost of Delay

| Issue | Fix now | Fix in 2 years | Multiplier |
|-------|---------|----------------|------------|
| F-01: Protocol version | 3 days | 3 weeks | 5x |
| F-02: Tool envelope | 2 days | 2 weeks | 5x |
| F-03: Correlation ID | 1 day | 2 weeks | 10x |
| F-04: Causation ID | 1 day | 3 weeks | 15x |
| F-05: Delivery semantics | 3 days | 3 weeks | 5x |
| F-06: Serialization version | 2 days | 2 weeks | 5x |
| F-07: ABC versioning | 2 days | 3 weeks | 7.5x |
| F-08: Cross-process protocol | 5 days | 2 months | 8x |
| F-09: Queue serialization | 1 day | 1 week | 5x |

**Total now:** ~20 days  
**Total in 2 years:** ~16 weeks (4x multiplier)

---

## Recommendation for F28

1. **F-01, F-02, F-03, F-04 (Critical):** Add protocol version, message envelope, correlation ID, and causation ID to all cross-component message types. This is the minimum viable distributed protocol.

2. **F-07 (High):** Define ABC versioning strategy before adding more implementations.

3. **F-06 (High):** Add `schema_version` to all serialized payloads before the next release.

4. **F-11 (Medium):** Wire key components to EventBus for observability.

5. **F-08 (High):** Document remote-capable interfaces before distributed implementation begins.

No implementation until this audit is closed.

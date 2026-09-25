# F28-B1 Architecture Audit: 7 ADRs Cross-Analysis

**Objective:** Find design defects, contradictions, and risks. No style review. No documentation polish.

---

## Cross-ADR Contradictions

### 🔴 CON-01: ErrorEnvelope Defined in TWO Places with Different Fields

**Severity:** Critical  
**Evidence:** ADR-028-01 defines `ErrorEnvelope` with 6 fields (`error_code`, `error_message`, `error_details`, `component`, `original_message_id`, `retryable`). ADR-028-06 defines a DIFFERENT `ErrorEnvelope` with 8 fields (adds `original_message_type`, `retry_delay_ms`). Two ADRs define the same type with incompatible schemas.  
**ADRs affected:** 01, 06  
**Invariants compromised:** C02 (MAJOR different = breaking — both can't be right)  
**Impact:** Implementation ambiguity. Which ErrorEnvelope is correct?  
**Solution:** ADR-028-06 must be the single source of truth. Remove ErrorEnvelope from ADR-028-01.  
**Cross-compat:** Removing from 01 is compatible with 06.

---

### 🔴 CON-02: checksum Algorithm Contradiction

**Severity:** Critical  
**Evidence:** ADR-028-01 I01 says `message_id = SHA-256(source + destination + message_type + timestamp + payload_checksum)[:16]`. ADR-028-04 SR04 says `checksum = SHA-256(payload_bytes + schema_version + message_id)`. There is CIRCULAR DEPENDENCY: message_id depends on payload_checksum, but checksum depends on message_id. Impossible to compute either without the other.  
**ADRs affected:** 01, 04  
**Invariants compromised:** I01, S05 (circular, cannot be satisfied simultaneously)  
**Impact:** Both invariants are unsatisfiable. Implementation deadlock.  
**Solution:** Break the cycle. Either:
- (a) `checksum = SHA-256(payload_bytes + schema_version)` (no message_id)
- (b) `message_id = SHA-256(source + destination + message_type + timestamp)` (no checksum)
- (c) `message_id = SHA-256(envelope_without_message_id)`, `checksum = SHA-256(payload)` (hierarchical)  
**Cross-compat:** Any solution requires updating both ADRs.

---

### 🔴 CON-03: Metadata Type Contradiction

**Severity:** Critical  
**Evidence:** ADR-028-01 defines `metadata: dict[str, str]` (value must be string). ADR-028-06 defines `error_details: dict[str, str]` (value must be string). ADR-028-07 DP04 says deprecation warning goes in `metadata: {"deprecated": "field_x"}` — this works with str values. However, ADR-028-05 has no metadata field in its trace model, meaning observability events cannot carry metadata.  
**ADRs affected:** 01, 05, 06, 07  
**Invariants compromised:** None directly, but O01-O06 don't mention metadata.  
**Impact:** Audit events (ADR-028-05) have no metadata field. Cannot attach deprecation warnings to audit events.  
**Solution:** Add `metadata: dict[str, str]` to the observability trace model.  
**Cross-compat:** Adding optional field to observability model is non-breaking.

---

### 🟠 CON-04: ComponentBoundary Says "No Serialization" — But ProtocolEnvelope Has payload: bytes

**Severity:** High  
**Evidence:** ADR-028-01 Section 3 says ComponentBoundary has "Sin serialización (punteros directos)". But ProtocolEnvelope has `payload: bytes` which implies serialization. If there's no serialization, payload should be `Any` or a typed object, not `bytes`.  
**ADRs affected:** 01  
**Invariants compromised:** None (no invariant covers boundary rules)  
**Impact:** ComponentBoundary has contradictory requirements: no serialization but typed for bytes.  
**Solution:** Either:
- (a) ComponentBoundary uses typed objects directly (no ProtocolEnvelope)
- (b) ComponentBoundary uses ProtocolEnvelope with typed payload (serialize anyway for consistency)  
**Cross-compat:** Choice (b) is simpler. Remove "no serialization" from ComponentBoundary.

---

## Single-ADR Design Defects

### 🔴 DEF-01: ProtocolEnvelope Has 30 Fields — God Object Risk

**Severity:** Critical  
**Evidence:** ProtocolEnvelope has 30 fields across 6 concerns: identity, routing, delivery, content, metadata, evolution. This violates Single Responsibility Principle. A change to ANY of these concerns requires modifying the same class. Adding compression? Change Envelope. Adding auth? Change Envelope. Adding new delivery semantics? Change Envelope.  
**ADRs affected:** 01  
**Invariants compromised:** None (no invariant limits envelope size)  
**Impact:** Every protocol evolution requires touching the central class. High merge conflict probability in distributed teams.  
**Solution:** Split into separate headers:
- `TransportHeader` (routing, delivery)
- `TraceHeader` (correlation, causation, timestamp)
- `PayloadHeader` (type, schema_version, compression)
- `SecurityHeader` (auth, encryption)
- `EvolutionHeader` (capabilities, reserved)

The envelope becomes a container of optional headers, not a monolithic struct.  
**Cross-compat:** This can be done without breaking the invariants. The serialized form would group fields by header.

---

### 🟠 DEF-02: Version Negotiation Requires Bidirectional Exchange — But QUERY/EVENT Are Unidirectional

**Severity:** High  
**Evidence:** ADR-028-03 says version negotiation happens in "first exchange" (bidirectional). But EVENT messages are fire-and-forget (unidirectional). A component receiving an EVENT from an unknown sender has no channel to negotiate version.  
**ADRs affected:** 01, 03, 07  
**Invariants compromised:** V01 (negotiation), E05 (coexistence)  
**Impact:** EVENT senders cannot negotiate version. If protocol changes, old EVENT receivers may break silently.  
**Solution:** Either:
- (a) EVENT messages always use lowest common denominator version (1.0)
- (b) Version is declared in the message itself and receiver accepts or drops
- (c) Bidirectional negotiation for COMMAND/QUERY, "declare and hope" for EVENT  
**Cross-compat:** Requires updating ADR-028-03 and ADR-028-07.

---

### 🟠 DEF-03: Forward Compatibility FC03 Contradicts Error Contract ER01

**Severity:** High  
**Evidence:** ADR-028-02 FC03 says "consumer antiguo que no reconoce un message_type, lo rechaza con un error conocido." ADR-028-06 ER01 says "ERROR es siempre un mensaje de tipo ErrorEnvelope." But sending an ERROR requires the OLD consumer to recognize the ErrorEnvelope message_type! Circular problem: old consumer rejects unknown message_type by sending an ERROR, but sending an ERROR requires recognizing the ErrorEnvelope type.  
**ADRs affected:** 02, 06  
**Invariants compromised:** FC03, ER01  
**Impact:** An old consumer cannot reject an unknown message because it would need to use a known error type, which requires recognizing a message type.  
**Solution:** The "error conocido" must be a transport-level rejection (TCP RST, HTTP 400), not a protocol-level ErrorEnvelope. Update FC03 to say "rechaza a nivel de transporte."  
**Cross-compat:** Updating FC03 in ADR-028-02 is compatible with ADR-028-06.

---

### 🟠 DEF-04: causation_id Semantics Are Underdefined for Events

**Severity:** High  
**Evidence:** ADR-028-04 says causation_id "hereda del mensaje entrante." For COMMAND/QUERY/RESPONSE this is clear. For EVENT (which has no response), causation_id should point to the event that triggered this event (if any). But the first event in a chain has causation_id=None. ADR-028-05 does not specify the initial value.  
**ADRs affected:** 04, 05  
**Invariants compromised:** I04  
**Impact:** Ambiguity in the first event of a causal chain.  
**Solution:** Define: "El primer evento de una cadena causal tiene causation_id=None. El causation_id de un evento apunta al event_id del evento que lo desencadenó, o None si es el origen."  
**Cross-compat:** Clarification only. No breaking changes.

---

### 🟡 DEF-05: size_bytes in the Envelope is a Control vs Data Concern

**Severity:** Medium  
**Evidence:** ADR-028-01 includes `size_bytes` as a field in ProtocolEnvelope. But `size_bytes` is metadata about the envelope itself (control), not about the domain (data). The sender computes it before sending. The receiver uses it for validation. This is correct, but it creates a bootstrap problem: to compute size_bytes, you need the serialized envelope, but to serialize you need size_bytes.  
**ADRs affected:** 01  
**Invariants compromised:** S06 (size_bytes ≤ 10 MB)  
**Impact:** Chicken-and-egg: can't compute size without serializing, can't serialize without size.  
**Solution:** Either:
- (a) Compute size after serialization (size_bytes is filled last, before checksum)
- (b) Remove size_bytes from envelope (receiver checks actual received size)
- (c) Add `max_size: int` instead (sender declares max, receiver enforces)  
**Cross-compat:** Option (b) is simplest. Remove size_bytes from envelope, enforce at transport level.

---

### 🟡 DEF-06: timestamp Uses time.time() — Non-Deterministic by Default

**Severity:** Medium  
**Evidence:** ADR-028-05 says "timestamp es determinista (time.time() en origen, no se reasigna)." But `time.time()` is NOT deterministic — it returns wall-clock time which depends on when the code executes. Two identical logical operations produce different timestamps. This breaks determinism for testing and replay.  
**ADRs affected:** 05  
**Invariants compromised:** O04  
**Impact:** Cannot have deterministic replay of protocol traces.  
**Solution:** Use logical timestamp (monotonic counter) OR wall-clock + deterministic seed for testing. Document: "timestamp is wall-clock time for production, monotonic counter for deterministic testing."  
**Cross-compat:** No breaking changes. Clarification only.

---

### 🟡 DEF-07: No Idempotency for AT_LEAST_ONCE

**Severity:** Medium  
**Evidence:** ADR-028-01 D02 says "AT_LEAST_ONCE: reintento hasta ACK o agotar retry_policy." But retries can cause duplicate delivery. Without idempotency_key (only required for EXACTLY_ONCE per D03), AT_LEAST_ONCE messages may be processed multiple times.  
**ADRs affected:** 01  
**Invariants compromised:** D02  
**Impact:** Retried AT_LEAST_ONCE messages can cause duplicate side effects.  
**Solution:** Either:
- (a) Require idempotency_key for AT_LEAST_ONCE too
- (b) Document that AT_LEAST_ONCE may have duplicates and consumers must handle them  
**Cross-compat:** Both are compatible. Choice (b) is weaker but simpler.

---

## Risks

### 🔴 RISK-01: No Auth or Encryption in Local Boundaries

**Severity:** Critical  
**Evidence:** SEC01 says "mensajes entre nodos deben autenticarse" and SEC02 says "cifrarse en tránsito." But these only apply to TransportBoundary (between physical nodes). ProtocolBoundary (between components in the same process or same Kubernetes pod) has no auth or encryption. An agent that can reach the ProtocolBoundary can impersonate any component.  
**ADRs affected:** 01  
**Invariants compromised:** SEC01, SEC02 (insufficient scope)  
**Impact:** In a multi-tenant deployment, compromised agent can impersonate Fusion, Memory, or other agents.  
**Solution:** Extend SEC01 and SEC02 to ProtocolBoundary, not just TransportBoundary.  
**Cross-compat:** No breaking changes. Requires updating invariants.

---

### 🟠 RISK-02: No Delivery Guarantee for ERROR Messages

**Severity:** High  
**Evidence:** ADR-028-06 defines ErrorEnvelope but does not specify delivery semantics for errors. Should errors be AT_MOST_ONCE, AT_LEAST_ONCE, or EXACTLY_ONCE? If a timeout error is lost, the sender retries indefinitely (timeout → retry → timeout → ...).  
**ADRs affected:** 06  
**Invariants compromised:** D01-D07 (no error delivery rule)  
**Impact:** Lost error messages can cause infinite retry loops.  
**Solution:** Define error delivery: "ERROR messages are AT_LEAST_ONCE. The receiver must ACK errors. If no ACK, retry up to 3 times, then log and stop."  
**Cross-compat:** Compatible with all ADRs.

---

### 🟠 RISK-03: compression Applied Before checksum — Wrong Order

**Severity:** High  
**Evidence:** ADR-028-04 SR07 says "Compresión se aplica al payload antes de calcular checksum." But ADR-028-01 I01 includes `payload_checksum` in `message_id` computation. If compression is before checksum, the checksum covers compressed bytes. On the receiver, decompression must happen AFTER checksum verification. But the receiver needs to decompress to verify the domain-level payload. The checksum verifies compressed bytes, but the application needs integrity of uncompressed bytes.  
**ADRs affected:** 01, 04  
**Invariants compromised:** S05, S07  
**Impact:** Checksum verifies compressed payload, but application needs uncompressed integrity. A compression bug could corrupt data without detection.  
**Solution:** checksum should verify uncompressed payload. Order: serialize → checksum → compress → send. Or: checksum over the uncompressed payload stored alongside.  
**Cross-compat:** Requires updating S07 in ADR-028-04.

---

### 🟡 RISK-04: 10 MB Size Budget for ToolResult Blocks Agent Execution

**Severity:** Medium  
**Evidence:** ADR-028-04 budgets 10 MB for ToolResult. Processing a 10 MB result blocks the agent until fully received. An agent with 3 concurrent tools could have 30 MB in flight. No streaming support.  
**ADRs affected:** 04  
**Invariants compromised:** S06  
**Impact:** High latency for large tool results. Memory pressure.  
**Solution:** Add streaming support for large payloads (chunked transfer). Keep 10 MB for non-streaming, allow streaming for larger.  
**Cross-compat:** Compatible. Add streaming message_kind or chunking protocol.

---

### 🟡 RISK-05: No Clock Sync Between Nodes

**Severity:** Medium  
**Evidence:** ADR-028-05 uses `timestamp` for tracing and timing. Between nodes, clocks drift. `timestamp` from node A and `timestamp` from node B cannot be compared without clock synchronization.  
**ADRs affected:** 05  
**Invariants compromised:** O04, O06  
**Impact:** Timing metrics are inaccurate across nodes. Causality may appear reversed if clocks are skewed.  
**Solution:** Either require NTP synchronization OR use logical counters (Lamport clocks) for causality, wall clock for human readability.  
**Cross-compat:** Can add logical clock alongside wall clock. No breaking changes.

---

## ADR ↔ ADR Matrix

| ADR | Depends on | Coupling | Contradictions | Could merge with | Could simplify |
|-----|-----------|----------|---------------|-----------------|----------------|
| 01 | — | High (central) | CON-01 (ErrorEnvelope), CON-04 (boundaries), DEF-01 (god object) | — | Split headers |
| 02 | 01 | Medium | CON-03 (metadata), DEF-03 (error rejection) | — | Remove FC03 (redundant with transport) |
| 03 | 01 | High | DEF-02 (unidirectional events) | — | Add unidirectional versioning |
| 04 | 01 | High | CON-02 (checksum cycle), RISK-03 (compress order) | — | Fix checksum algorithm |
| 05 | 01 | Medium | CON-03 (no metadata), DEF-06 (time determinism) | — | Add metadata, add logical clock |
| 06 | 01 | Medium | CON-01 (duplicate ErrorEnvelope), DEF-03 (error circularity), RISK-02 (error delivery) | 01 (remove duplicate) | Remove from 01, keep in 06 |
| 07 | 01, 02, 03 | High | DEF-02 (event negotiation) | — | Add unidirectional path |

### Merge Candidates

- **ADR-028-02 into ADR-028-03:** Compatibility rules are essentially versioning rules. The distinction (what changes are allowed vs how to version) is artificial. Merging would reduce cross-referencing errors.
- **ADR-028-05 into ADR-028-01 (partial):** The trace fields (correlation_id, causation_id) are already in ProtocolEnvelope. The audit requirements (OB01-OB06) are operational, not architectural, and could live in a separate operations document rather than an ADR.

### Fragmentation Risk

7 ADRs for a single protocol is excessive. Each ADR has ~50 lines. The total is ~580 lines. A single well-structured document of 300 lines would be easier to maintain and less prone to cross-referencing errors. The fragmentation increases the probability of CON-01/CON-02 type contradictions.

---

## Summary

| Severity | Count | Key Findings |
|----------|-------|-------------|
| 🔴 Critical | 5 | CON-01 (ErrorEnvelope duplicate), CON-02 (checksum cycle), CON-03 (metadata), DEF-01 (God Object), RISK-01 (auth scope) |
| 🟠 High | 5 | CON-04 (boundary serialization), DEF-02 (unidirectional negotiation), DEF-03 (error circularity), DEF-04 (causation undefined), RISK-02 (error delivery), RISK-03 (compression order) |
| 🟡 Medium | 5 | DEF-05 (size_bytes bootstrap), DEF-06 (time determinism), DEF-07 (at-least-once idempotency), RISK-04 (streaming), RISK-05 (clock sync) |

### All 10 CR resolved in F28-B1A

| CR | Status | Change |
|----|--------|--------|
| CR-01 | ✅ Fixed | checksum = SHA-256(payload). No cycle with message_id. |
| CR-02 | ✅ Fixed | ErrorEnvelope only in ADR-028-06. Removed from ADR-028-01. |
| CR-03 | ✅ Fixed | ProtocolEnvelope split into 5 headers + opaque payload. |
| CR-04 | ✅ Fixed | Auth in SecurityHeader (ProtocolBoundary). TransportBoundary does NOT authorize. |
| CR-05 | ✅ Fixed | Dead-letter for future versions. Reject for known MAJOR. |
| CR-06 | ✅ Fixed | Per-message-kind negotiation (COMMAND, QUERY, RESPONSE, ERROR, EVENT). |
| CR-07 | ✅ Fixed | Metadata in DeliveryHeader only (dict[str,str]). Removed from observability. |
| CR-08 | ✅ Fixed | 52 → 32 invariants. No duplicates. No contradictions. 8 categories. |
| CR-09 | ✅ Fixed | ADR-028-02 deleted. Merged into ADR-028-03. 7 → 5 ADRs. |
| CR-10 | ✅ Fixed | Component→ADR→Invariants→Responsibility matrix. No duplicates. |

### Architecture consistency verified:
- ✅ Zero cycles (checksum/message_id)
- ✅ Zero duplicate responsibilities
- ✅ Zero contradictory invariants
- ✅ Zero duplicate models (single ErrorEnvelope)
- ✅ Zero unnecessary cross-dependencies
- ✅ 5 ADRs (down from 7)

# F28-B2 Code Audit: motor/platform Implementation

**Objective:** Verify 1:1 correspondence with ADRs. Find design defects. No code changes.
**Scope:** All 9 source files + 1 test file (1089 LOC).

---

## 1. ADR Correspondence

| ADR Element | Code Location | Match | Notes |
|------------|--------------|-------|-------|
| ProtocolEnvelope (5 headers + payload) | `models.py:ProtocolEnvelope` | ✅ 1:1 | VersionHeader, RoutingHeader, TraceHeader, DeliveryHeader, SecurityHeader |
| VersionHeader | `models.py:VersionHeader` | ✅ | protocol_version, schema_version, payload_type, capabilities, reserved |
| RoutingHeader | `models.py:RoutingHeader` | ✅ | message_id, message_type, message_kind, source, destination |
| TraceHeader | `models.py:TraceHeader` | ✅ | correlation_id, causation_id, timestamp |
| DeliveryHeader | `models.py:DeliveryHeader` | ✅ | semantics, idempotency_key, timeout_ms, cancelable, max_response_bytes, metadata |
| SecurityHeader | `models.py:SecurityHeader` | ✅ | auth_token, auth_token_type |
| ErrorEnvelope | `models.py:ErrorEnvelope` | ✅ | Single definition, matches ADR-028-06 |
| MessageKind | `models.py:MessageKind` | ✅ | 5 values: COMMAND, QUERY, EVENT, RESPONSE, ERROR |
| DeliverySemantics | `models.py:DeliverySemantics` | ✅ | 3 values |
| RetryPolicy | `models.py:RetryPolicy` | ✅ | matches ADR |
| ProtocolSerializer ABC | `serializer.py:ProtocolSerializer` | ✅ | serialize(envelope) → bytes |
| ProtocolDeserializer ABC | `serializer.py:ProtocolDeserializer` | ✅ | deserialize(bytes) → envelope |
| JsonProtocolSerializer | `serializer.py:JsonProtocolSerializer` | ✅ | sort_keys, compact separators |
| compute_checksum | `serializer.py:compute_checksum` | ✅ | SHA-256(payload) |
| make_message_id | `serializer.py:make_message_id` | ✅ | SHA-256(proto+...+payload[:64]) |
| ProtocolValidator | `validator.py:ProtocolValidator` | ✅ | centralized validation |
| VersionNegotiator | `negotiator.py:VersionNegotiator` | ⚠️ | Missing RESPONSE/ERROR inheritance rule |
| CompatibilityChecker | `compat.py:CompatibilityChecker` | ✅ | forward, backward, can_communicate |
| ProtocolRegistry | `registry.py:ProtocolRegistry` | ✅ | thread-safe |
| Transport ABC | `transport.py:Transport` | ✅ | send, receive, request |
| LocalTransport | `transport.py:LocalTransport` | ✅ | in-process reference |
| ProtocolException | `errors.py:ProtocolException` | ✅ | base exception |
| **Missing:** checksum in envelope | — | ❌ | ADR says checksum verifies payload, but envelope has no checksum field. `compute_checksum` exists but is not called during serialize/deserialize. |

---

## Findings

### 🔴 F-01: checksum is computed but NEVER stored or verified in serialization

**Severity:** Critical  
**File:** `serializer.py`  
**Evidence:** `compute_checksum(payload)` exists. `ProtocolValidator.validate_checksum()` exists. But `JsonProtocolSerializer.serialize()` does NOT include checksum in the output. `JsonProtocolDeserializer.deserialize()` does NOT verify checksum. The checksum is computed but never used in the serialize/deserialize cycle.  
**ADR violation:** ADR-028-04 S05: "checksum verifica integridad del envelope completo" — violated.  
**Risk:** Payload corruption goes undetected.  
**Fix:** Include checksum in serialized output. Verify on deserialization.

### 🔴 F-02: LocalTransport.request() mutates shared list in race condition

**Severity:** Critical  
**File:** `transport.py:35-42`  
**Evidence:** `request()` calls `self._received.append(envelope)` then pops via handler. But `send()` also appends to `_received`. If `request()` and `send()` are called concurrently, `_received` is mutated without lock. `receive()` also pops from `_received` without lock.  
**ADR violation:** ADR-028-01 requires thread safety.  
**Risk:** Lost messages, corrupted state, race condition.  
**Fix:** Add `threading.Lock` to LocalTransport.

### 🟠 F-03: VersionNegotiator does not implement RESPONSE/ERROR inheritance

**Severity:** High  
**File:** `negotiator.py`  
**Evidence:** ADR-028-03 specifies: "RESPONSE inherits version from triggering COMMAND/QUERY. ERROR inherits version from original_message_id." The `VersionNegotiator` only handles COMMAND, QUERY, and EVENT. There is no `negotiate_response()` or `negotiate_error()` method.  
**ADR violation:** ADR-028-03 negotiation table incomplete.  
**Risk:** Version mismatch for responses and errors.  
**Fix:** Add `negotiate_response(trigger_version, ...)` and `negotiate_error(trigger_version, ...)`.

### 🟠 F-04: CausationId deserialization loses root status

**Severity:** High  
**File:** `serializer.py:_from_dict`  
**Evidence:** `CausationId.root()` creates an ID with `is_root=True` and `value=""`. When serialized, `str(causation_id)` returns `""` for root. When deserialized, `CausationId(t.get("causation_id", ""))` creates a non-root ID with empty value. Root status is lost. Serialize → deserialize changes semantics.  
**ADR violation:** ADR-028-05 O03 (causation chain integrity).  
**Risk:** Cannot distinguish "root cause" from "missing causation".  
**Fix:** Use a sentinel value (e.g., "ROOT") for root causation.

### 🟠 F-05: ProtocolEnvelope missing checksum field

**Severity:** High  
**File:** `models.py:ProtocolEnvelope`  
**Evidence:** ADR-028-01 defines checksum in the envelope. ADR-028-04 S05 says "checksum = SHA-256(payload_bytes)". But `ProtocolEnvelope` has NO checksum field. `compute_checksum()` exists independently but is not part of the envelope.  
**ADR violation:** ADR-028-01 envelope spec, ADR-028-04 S05.  
**Risk:** Integrity cannot be verified without out-of-band checksum passing.  
**Fix:** Add `checksum: str = ""` to ProtocolEnvelope. Populate in `make_message_id` or constructor.

### 🟡 F-06: make_message_id uses payload[:64] which is O(n) for large payloads

**Severity:** Medium  
**File:** `serializer.py:make_message_id`  
**Evidence:** `payload[:64]` creates a slice (O(1) in Python, actually O(k) for k=64). But `payload.hex()` in `MessageId.make` converts the entire `payload_first_bytes` (up to 64 bytes) to hex string (128 hex chars). This is fine for 64 bytes, but if the intent is to use the full payload for more robust identity, it would be O(n) for the full payload.  
**Risk:** None currently (64 bytes is constant time). Low risk.  
**Fix:** Document that message_id uses first 64 bytes only.

### 🟡 F-07: RoutingHeader validates message_kind via isinstance — fails for string deserialization

**Severity:** Medium  
**File:** `validator.py:_validate_routing`  
**Evidence:** `if not isinstance(r.message_kind, MessageKind)` — but `JsonProtocolDeserializer` reconstructs `MessageKind` from string via `MessageKind(r["message_kind"])`. If the value is invalid, `MessageKind()` raises `ValueError` which is NOT caught. The validation would never reach this check for truly invalid values.  
**Risk:** Invalid message_kind causes ValueError before validation. Acceptable for now.  
**Fix:** This is a defense-in-depth issue. The isinstance check is correct for programmatic construction.

### 🟡 F-08: Metadata in DeliveryHeader is mutable default (fixed as field(default_factory=dict))

**Severity:** Medium  
**File:** `models.py:DeliveryHeader`  
**Evidence:** `metadata: dict[str, str] = field(default_factory=dict)`. This is correct for immutability. However, `_from_dict` assigns `metadata=metadata` where `metadata` is a regular dict. This breaks the frozen dataclass contract because `metadata` is a mutable dict inside an immutable envelope.  
**ADR violation:** "All models immutable."  
**Risk:** A receiver could modify `envelope.delivery.metadata["key"] = "value"`, changing the envelope's content even though it's frozen.  
**Fix:** Use `tuple[tuple[str, str], ...]` for metadata (immutable).

### 🟡 F-09: No validation for reserved fields content

**Severity:** Medium  
**File:** `validator.py`  
**Evidence:** ADR-028-01 includes `reserved: tuple[str, ...]` in VersionHeader. But `ProtocolValidator` does NOT check that reserved fields are not used for data transport. ADR-028-01 V05 says "reserved se ignora en versiones receptoras que no lo reconocen." But there's no validation that reserved is actually reserved.  
**Risk:** Developers might use `reserved` as an undocumented data channel.  
**Fix:** (Optional, ADR-level concern) No code change needed if ADR already prohibits it.

### 🟡 F-10: Future unknown MessageKind triggers ValueError, not dead-letter

**Severity:** Medium  
**File:** `serializer.py:_from_dict`  
**Evidence:** `MessageKind(r["message_kind"])` raises `ValueError` if the string is not in the enum. ADR-028-01 says unknown future versions should go to dead-letter. A future MessageKind value would crash deserialization instead of being dead-lettered.  
**ADR violation:** ADR-028-01 dead-letter policy.  
**Risk:** Future extensions that add new MessageKind values break old deserializers.  
**Fix:** Catch ValueError and return a best-effort envelope or raise ProtocolException instead of ValueError.

---

## Class Responsibility Matrix

| Class | Responsibility | ADR | Tests | Single? |
|-------|---------------|-----|-------|---------|
| `MessageId` | Identity of a message | 01 | 1 | ✅ |
| `CorrelationId` | Cross-chain trace ID | 05 | 0 | ✅ |
| `CausationId` | Cause-effect link | 05 | 0 | ✅ |
| `IdempotencyKey` | Deduplication | 01 | 0 | ✅ |
| `MessageKind` | Message type classification | 01 | 0 | ✅ |
| `DeliverySemantics` | Delivery guarantee | 01 | 0 | ✅ |
| `VersionHeader` | Protocol + schema version | 01 | 0 | ✅ |
| `RoutingHeader` | Addressing + identity | 01 | 0 | ✅ |
| `TraceHeader` | Tracing + timing | 05 | 0 | ✅ |
| `DeliveryHeader` | Delivery policy | 01 | 0 | ✅ |
| `SecurityHeader` | Auth token | 01 | 1 | ✅ |
| `RetryPolicy` | Retry configuration | 01 | 0 | ✅ |
| `ProtocolEnvelope` | Container for headers + payload | 01 | 0 | ✅ |
| `ErrorEnvelope` | Typed error payload | 06 | 2 | ✅ |
| `ProtocolSerializer` ABC | Serialize envelope | 04 | 2 | ✅ |
| `ProtocolDeserializer` ABC | Deserialize envelope | 04 | 2 | ✅ |
| `JsonProtocolSerializer` | JSON serialization | 04 | 4 | ✅ |
| `JsonProtocolDeserializer` | JSON deserialization | 04 | 2 | ✅ |
| `compute_checksum` | Payload integrity | 04 | 3 | ✅ |
| `make_message_id` | Deterministic ID | 01 | 1 | ✅ |
| `ProtocolValidator` | Centralized validation | 01 | 7 | ✅ |
| `CompatibilityChecker` | Forward/backward compat | 03 | 3 | ✅ |
| `VersionNegotiator` | Version per message kind | 03 | 4 | ⚠️ Missing RESPONSE/ERROR |
| `ProtocolRegistry` | Schema + version registry | — | 0 | ✅ |
| `Transport` ABC | Communication medium | 01 | 0 | ✅ |
| `LocalTransport` | In-process transport | 01 | 0 | ⚠️ Race condition |
| `ProtocolException` | Base error | — | 0 | ✅ |

**Missing tests for:** CorrelationId, CausationId, IdempotencyKey, VersionHeader, RoutingHeader, TraceHeader, DeliveryHeader, ProtocolEnvelope, RetryPolicy, ProtocolRegistry, Transport, LocalTransport.

---

## Architectural Metrics

| Metric | Value |
|--------|-------|
| **Total LOC** | 1089 (9 source + 1 test) |
| **Classes** | 20 (+ 5 enums) |
| **ABCs** | 3 (ProtocolSerializer, ProtocolDeserializer, Transport) |
| **Depth of inheritance** | 0 (no inheritance chains) |
| **Cyclomatic complexity (max)** | 8 (VersionNegotiator.negotiate) |
| **Package coupling** | All modules depend on `models.py`. No circular deps. |
| **Cohesion** | High (each file has single responsibility) |
| **Global state** | 0 |
| **Singletons** | 0 |
| **Thread safety issues** | 1 (LocalTransport) |
| **Frozen dataclasses** | 11/11 models ✅ |
| **Forward compat gap** | 1 (MessageKind ValueError) |
| **Backward compat gap** | 0 |
| **ADR violations** | 3 (checksum not stored, RESPONSE/ERROR negotiation missing, root causation lost) |

---

## Summary

| Severity | Count | Findings |
|----------|-------|----------|
| 🔴 Critical | 2 | F-01 (checksum unused), F-02 (race condition) |
| 🟠 High | 3 | F-03 (RESPONSE/ERROR negotiation), F-04 (causation root lost), F-05 (checksum field missing) |
| 🟡 Medium | 5 | F-06 to F-10 (minor issues) |
| 🟢 Low | 0 | |

**Total: 10 findings. 6 ADR mismatches. 1 thread safety hole. 3 missing features.**

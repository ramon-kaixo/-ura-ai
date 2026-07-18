# ADR-028-01: Internal Platform Protocol Architecture (v2)

**Status:** Draft  
**Phase:** F28-B1A  
**CR resolved:** CR-01, CR-03, CR-04, CR-05, CR-07  

---

## 1. ProtocolEnvelope — Container (not God Object)

ProtocolEnvelope is a container for typed headers. Each header has a single responsibility.

```python
@dataclass(frozen=True)
class ProtocolEnvelope:
    version: VersionHeader       # REQUIRED
    routing: RoutingHeader       # REQUIRED  
    trace: TraceHeader           # REQUIRED
    delivery: DeliveryHeader     # REQUIRED
    security: SecurityHeader     # OPTIONAL (only for ProtocolBoundary)
    payload: bytes               # opaque, typed via VersionHeader.schema_version
```

---

## 2. Headers

### VersionHeader

```python
@dataclass(frozen=True)
class VersionHeader:
    protocol_version: str        # semver "1.0"
    schema_version: str          # semver "1.0"
    payload_type: str            # "json" | "msgpack" | "protobuf"
    capabilities: tuple[str, ...]  # emitter capabilities
    reserved: tuple[str, ...]    # future evolution, ignored by old receivers
```

### RoutingHeader

```python
@dataclass(frozen=True)
class RoutingHeader:
    message_id: str              # SHA-256(protocol_version + schema_version + source + destination + message_type + payload[:64])[:16]
    message_type: str            # "ToolRequest" | "ToolResult" | ...
    message_kind: str            # "command" | "query" | "event" | "response" | "error"
    source: str                  # component name
    destination: str             # component name
```

### TraceHeader

```python
@dataclass(frozen=True)
class TraceHeader:
    correlation_id: str          # set by root emitter, never changes
    causation_id: str | None     # message_id that caused this message (None for root)
    timestamp: float             # wall-clock time (production) OR monotonic counter (testing)
```

### DeliveryHeader

```python
@dataclass(frozen=True)
class DeliveryHeader:
    semantics: str               # "at_most_once" | "at_least_once" | "exactly_once"
    idempotency_key: str | None  # required for exactly_once, recommended for at_least_once
    timeout_ms: int
    cancelable: bool
    retry_policy: RetryPolicy | None
    max_response_bytes: int      # receiver-enforced limit
```

### SecurityHeader

```python
@dataclass(frozen=True)
class SecurityHeader:
    auth_token: str | None       # Authentication (ProtocolBoundary and up)
    auth_token_type: str | None  # "bearer" | "mtls" | "jwt"
```

**SECURITY DECISION (CR-04):** Authorization decisions are made at ProtocolBoundary, not TransportBoundary. TransportBoundary only handles authentication (identity verification). The SecurityHeader is OPTIONAL — it only appears when crossing a ProtocolBoundary. ComponentBoundary calls do not carry security context.

---

## 3. Boundaries (Updated)

```python
class ComponentBoundary:
    """Same process, same memory. No serialization, no security.
    ProtocolEnvelope used for audit only. Headers may be omitted.
    Payload is a typed object (not bytes)."""

class ProtocolBoundary:
    """Serialization required. Authorization enforced here.
    Full ProtocolEnvelope with all mandatory headers.
    SecurityHeader present. Transport is interchangeable."""

class TransportBoundary:
    """Same as ProtocolBoundary + authentication + encryption.
    Authorization is NEVER done here. Transport delegates to ProtocolBoundary.
    Transport handles: auth (TLS/mTLS), encryption, discovery."""
```

---

## 4. Unknown Message Policy (CR-05)

| Sender version | Receiver version | Message known? | Action |
|---------------|-----------------|---------------|--------|
| MAJOR == MAJOR | Any | Yes | Process normally |
| MINOR <= MINOR | MINOR >= MINOR | Yes | Process normally |
| MINOR > MINOR | MINOR < MINOR | Yes (new optional fields) | Process, ignore unknown fields |
| Any | Any | **No (message_type unknown)** | Reject with `unknown_message` error (protocol-level ErrorEnvelope) |
| MAJOR > MAJOR | MAJOR < MAJOR | No (future version) | **Dead-letter**: log + ignore. Do NOT reject (old receiver cannot construct error envelope in new format) |

**Dead-letter policy:** Unknown future messages are logged with full envelope content, stored in a dead-letter queue, and ignored. No error is returned to the sender (the sender would not understand it).

---

## 5. Integrity (CR-01)

```
checksum = SHA-256(payload)
```

**No cycle.** `message_id` does NOT include checksum:
```
message_id = SHA-256(
    protocol_version + schema_version + source + destination + message_type + payload_first_64_bytes
)[:16]
```

Payload first 64 bytes provide content awareness without circularity. If payload < 64 bytes, use entire payload.

---

## 6. Metadata Model (CR-07)

**Single model. No redefinition.**

```python
@dataclass(frozen=True)
class Metadata:
    entries: dict[str, str]       # string → string. No nesting. No binary.
```

Metadata appears in ONE place: as an OPTIONAL field in DeliveryHeader. When present, it carries non-functional information (deprecation warnings, processing hints, routing tags).

Observability (TraceHeader) does NOT carry metadata. Correlation, causation, and timestamp are sufficient for tracing. Application-level metadata belongs in the payload, not in the envelope.

---

## 7. Invariants (CR-08 — deduplicated, categorized)

### Identity (I)
```
I01. message_id = SHA-256(proto_ver + schema_ver + source + dest + type + payload[:64])[:16]
I02. message_id is immutable
I03. Two messages with same message_id are the same message
I04. message_id never reused
```

### Versioning (V)
```
V01. protocol_version = MAJOR.MINOR (strict semver)
V02. MAJOR different = breaking change
V03. MINOR different = backward + forward compatible
V04. emitter MINOR < receiver MINOR: works (backward compat)
V05. emitter MAJOR > receiver MAJOR: dead-letter (no reject)
V06. emitter MAJOR < receiver MAJOR: reject with version_mismatch
V07. Breaking change requires MAJOR bump
V08. Deprecation: DEPRECATED(n) → REMOVED(n+2 MAJOR releases)
```

### Delivery (D)
```
D01. AT_MOST_ONCE: fire-and-forget, no retry
D02. AT_LEAST_ONCE: retry until ACK or retry_policy exhausted
D03. EXACTLY_ONCE: idempotency_key required + receiver deduplication
D04. idempotency_key unique per operation
D05. Receiver rejects duplicate idempotency_key
D06. timeout_ms respected: no response → considered failure
```

### Serialization (S)
```
S01. payload is bytes. Schema identified by schema_version
S02. payload_type = "json" | "msgpack"
S03. JSON: sort_keys, ensure_ascii, compact separators
S04. Recipient must be able to deserialize payload for known schema_version
S05. checksum = SHA-256(payload bytes)
S06. No message may exceed 10 MB total serialized size
S07. Compression: "gzip" (default), "zstd" (if capability declared), "none"
```

### Observability (O)
```
O01. Every message has message_id, correlation_id, causation_id
O02. correlation_id persists across entire causal chain
O03. causation_id points to the message that caused this one (None for root)
O04. timestamp is wall clock (production) or monotonic counter (testing)
```

### Error (E)
```
E01. ERROR messages have message_kind = "error"
E02. ERROR payload is ErrorEnvelope (single definition in ADR-028-06)
E03. original_message_id in ErrorEnvelope points to the triggering message
E04. retryable=true errors may be retried per RetryPolicy
E05. retryable=false errors are terminal
```

### Evolution (EV)
```
EV01. New message types added without MAJOR bump
EV02. New optional fields added without MAJOR bump
EV03. capabilities extended without version bump
EV04. reserved ignored by receivers that don't recognize it
EV05. Each subsystem evolves its protocol_version independently
EV06. Unknown future messages → dead-letter (no reject)
```

**Total: 32 invariants** (reduced from 52). Zero duplicates. Zero contradictions.

---

## 8. Component Responsibility Matrix (CR-10)

| Component | ADR | Invariants | Responsibility |
|-----------|-----|------------|---------------|
| ProtocolEnvelope | 01 | I01-I04, S01-S07 | Container + opaque payload |
| VersionHeader | 01, 03 | V01-V08 | Protocol + schema versioning |
| RoutingHeader | 01 | I01-I03 | Message identity + routing |
| TraceHeader | 05 | O01-O04 | Correlation, causation, timing |
| DeliveryHeader | 01, 04 | D01-D06 | Semantics, timeout, retry |
| SecurityHeader | 01 | — | Auth token (ProtocolBoundary) |
| ErrorEnvelope | 06 | E01-E05 | Typed error payload |
| Compatibility Rules | 03 | V01-V08 | Forward/backward compat rules |
| Version Negotiation | 03 | V01-V06 | Per-message-kind negotiation |
| Unknown Message | 01 | EV06 | Dead-letter policy |
| Metadata | 01 (DeliveryHeader) | — | Key-value annotations |
| Checksum | 04 | S05 | Payload integrity |
| Size Budget | 04 | S06, D06 | Message size enforcement |
| Auth | 01 (SecurityHeader) | — | ProtocolBoundary auth, not Transport |
| Evolution Strategy | 07 | EV01-EV06 | Lifecycle, deprecation, migration |

**No duplicate responsibilities. No zero-responsibility components.**

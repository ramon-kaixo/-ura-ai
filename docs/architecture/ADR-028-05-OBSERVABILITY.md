# ADR-028-05: Observability Contract (v2)

**Status:** Draft  
**Phase:** F28-B1A  
**CR resolved:** CR-07 (metadata removed from observability)  

---

## Trace Model

TraceHeader in ProtocolEnvelope carries all observability fields:
- `correlation_id`: set by root emitter, never changes
- `causation_id`: message_id that caused this message (None for root)
- `timestamp`: wall clock (production), monotonic counter (testing)

No metadata in TraceHeader. Application-level annotations go in DeliveryHeader.metadata.

## Fields

| Field | Header | Purpose | Set by |
|-------|--------|---------|--------|
| `message_id` | RoutingHeader | Identity | Emitter |
| `correlation_id` | TraceHeader | Cross-chain trace | Root emitter |
| `causation_id` | TraceHeader | Cause-effect | Emitter (from incoming message_id) |
| `source` | RoutingHeader | Origin | Emitter |
| `destination` | RoutingHeader | Target | Emitter |
| `timestamp` | TraceHeader | Creation time | Emitter |
| `message_kind` | RoutingHeader | Message type classification | Emitter |

## Audit Requirements

```
OB01. Every message sent must be logged by sender's AuditLogger
OB02. Every message received must be logged by receiver's AuditLogger
OB03. AuditLogger indexes by correlation_id
OB04. AuditLogger indexes by source + destination
OB05. AuditLogger indexes by message_kind
OB06. Processing time derived from timestamp_difference
```

## Exception

EVENT messages: sender-side audit only (no bilateral audit).

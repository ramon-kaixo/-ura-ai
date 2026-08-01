# ADR-028-04: Serialization Contract (v2)

**Status:** Approved  
**Phase:** F28-B1A  
**CR resolved:** CR-01 (checksum), CR-07 (metadata)  
**Approved:** 2026-07-19  
**Verification:** All SR01-SR07 implemented in `motor/platform/serializer.py` and `motor/platform/validator.py`. Schema registry in `motor/platform/registry.py`. Size budgets enforced in `ProtocolValidator.SIZE_BUDGETS`. Checksum SHA-256 verified before decompression (P1 fix). Compression gzip implemented, zstd raises NotImplementedError. msgpack payload_type registered but not yet implemented — backward compatible.  

---

## Schema Registry

```
schema_version = "MAJOR.MINOR"

Registry:
  "ToolRequest": { "1.0": {...}, "1.1": {...} }
```

- MAJOR bump: payload incompatible
- MINOR bump: compatible (optional fields)
- Registry is a versioned JSON file in the repo
- Recipient deserializes with MAJOR ≤ its schema_version

## Payload Integrity

```
checksum = SHA-256(payload_bytes)
```

- checksum covers uncompressed payload bytes
- checksum is verified BEFORE decompression (transport layer) AND AFTER (application layer)
- No message_id dependency. No circularity.

## Serialization Rules

```
SR01. payload_type = "json" | "msgpack"
SR02. JSON: sort_keys=True, ensure_ascii=False, separators=(",",":")
SR03. checksum = SHA-256(payload_bytes)
SR04. max envelope size: 10 MB (enforced by receiver)
SR05. compression BEFORE checksum: serialize → compress → checksum → send
SR06. receiver: receive → verify checksum → decompress → verify checksum (application)
SR07. compression: "gzip" (default), "zstd" (if capability declared), "none"
```

## Message Size Budgets

| Type | Max | Enforcement |
|------|-----|-------------|
| ProtocolEnvelope (headers) | 1 KB | Sender |
| ToolRequest payload | 1 MB | Receiver |
| ToolResult payload | 10 MB | Receiver |
| MemoryEntry | 10 MB | Receiver |
| AgentAuditRecord | 1 MB | Sender |
| Event (EventBus) | 100 KB | Transport |

## Metadata

Metadata is OPTIONAL in DeliveryHeader only. Not in payload, not in TraceHeader.
Values are `dict[str, str]` (flat, strings only). No nesting. No binary.

## Payload Evolution

```python
# v1.0
@dataclass
class ToolRequestPayload:
    tool_name: str
    params: dict

# v1.1 (optional field added)
@dataclass
class ToolRequestPayload:
    tool_name: str
    params: dict
    timeout_ms: int | None = None
```

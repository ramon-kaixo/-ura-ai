# ADR-028-06: Error Contract (v2)

**Status:** Draft  
**Phase:** F28-B1A  
**CR resolved:** CR-02 (single ErrorEnvelope definition)  

---

## ErrorEnvelope — CANONICAL DEFINITION

This is the ONLY definition of ErrorEnvelope in the entire protocol. ADR-028-01 does not define ErrorEnvelope.

```python
@dataclass(frozen=True)
class ErrorEnvelope:
    error_code: str                # See canonical codes below
    error_message: str             # Human-readable
    error_details: dict[str, str]  # Additional context (string key-value)
    component: str                 # Source component
    original_message_id: str       # Message that caused this error
    original_message_type: str     # Type of the original message
    retryable: bool                # true → may retry
    retry_delay_ms: int            # Suggested delay before retry
```

## Canonical Error Codes

| Code | Retryable | Meaning |
|------|-----------|---------|
| `timeout` | ✅ Yes | Exceeded timeout limit |
| `unavailable` | ✅ Yes | Component temporarily unavailable |
| `transient` | ✅ Yes | Temporary processing error |
| `invalid_payload` | ❌ No | Malformed payload |
| `unauthorized` | ❌ No | Missing or invalid permissions |
| `not_found` | ❌ No | Resource not found |
| `oversized` | ❌ No | Message exceeds size budget |
| `version_mismatch` | ❌ No | MAJOR protocol version mismatch |
| `capacity_exceeded` | ✅ Yes | Queue full, budget exhausted |
| `unknown_message` | ❌ No | message_type not recognized |
| `internal_error` | ✅ Yes | Unexpected internal error |

## Error Delivery Rules

```
ER01. ERROR messages are AT_LEAST_ONCE (receiver must ACK)
ER02. If ERROR ACK not received → retry up to 3 times → silent discard
ER03. original_message_id must point to the triggering message
ER04. ERROR causation_id inherits from original_message
ER05. retryable=false errors: do NOT retry, do NOT dead-letter
ER06. retryable=true errors: retry per RetryPolicy
ER07. Domain errors (TOOL_ERROR, LLM_ERROR, PERMISSION_DENIED): non-retryable
ER08. Transport errors (ToolTimeoutError, ToolTransientError): retryable
```

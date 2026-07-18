# ADR-028-08: Platform Security — Inter-Subsystem Authentication

**Status:** Draft  
**Phase:** F28-B3  

---

## Problem

Today, all F24–F27 components run in the same process and trust each other implicitly.
`SecurityHeader` exists in `ProtocolEnvelope` but no component uses it.
In a multi-process or multi-node deployment, any component can impersonate any other.

## Decision

### Authentication Matrix

| From \ To | F24 Web | F25 Fusion | F26 Memory | F27 Agents | F28 Protocol |
|-----------|---------|------------|------------|------------|--------------|
| **F24 Web** | — | None (same proc) | None | None | Token |
| **F25 Fusion** | None | — | **Token** (write) | **Token** (read) | Token |
| **F26 Memory** | None | None | — | **Token** (read) | Token |
| **F27 Agents** | **Token** (search) | **Token** (read) | **Token** (write) | — | Token |
| **F28 Protocol** | Token | Token | Token | Token | Token |

**Legend:**
- None = same process, no auth
- Token = bearer token required

### Token Model

```python
@dataclass(frozen=True)
class ServiceIdentity:
    service: str        # "fusion" | "memory" | "agents" | "web"
    instance_id: str    # unique per instance
    capabilities: frozenset[str]  # what this service can do
    issued_at: float
    expires_at: float | None
```

- Tokens are issued by a local `IdentityManager` at startup
- In single-process mode: identity is implicit (no token check)
- In multi-process mode: tokens are passed via `SecurityHeader.auth_token`
- Token validation: `ProtocolValidator.validate_auth(token, required_service)`

### Rules

```
SEC01. In single-process mode: no auth required (performance optimization)
SEC02. In multi-process mode: ALL cross-process calls require auth
SEC03. Token contains: service, instance_id, capabilities, expiry
SEC04. Token is verified by the receiving component before processing
SEC05. Token mismatch → error "unauthorized" with original_message_id
SEC06. Capabilities are a subset of receiver's trust policy
SEC07. Token issuer is the platform bootstrap (not an external IdP initially)
```

### Implementation Plan

1. Add `IdentityManager` to `motor.platform` (issues/verifies tokens)
2. Wire `SecurityHeader` into `LocalTransport.request()` for multi-process mode
3. Add token validation to `ProtocolValidator`
4. No changes to existing F24–F27 single-process code paths

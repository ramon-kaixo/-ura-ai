# ADR-028-09: Platform Unified Configuration

**Status:** Draft  
**Phase:** F28-B3  

---

## Problem

Today there are 5+ separate configuration mechanisms:
- `core/config_manager.py` (global dict)
- `motor/core/fusion/config.py` (FusionConfig dataclass)
- `motor/agents/models.py` (AgentPolicy dataclass)
- `motor/platform/registry.py` (in-memory registry)
- Hardcoded parameters in constructors

No reload. No validation. No cross-reference.

## Decision

### Single Source of Truth: `PlatformConfig`

```python
@dataclass(frozen=True)
class PlatformConfig:
    # Protocol
    protocol_version: str = "1.0"
    max_payload_bytes: int = 10 * 1024 * 1024
    default_timeout_ms: int = 30000

    # Fusion (F25)
    fusion_max_claims: int = 50
    fusion_min_confidence: float = 0.3

    # Memory (F26)
    memory_snapshot_interval: int = 10000
    memory_retention_days: int = 365

    # Agents (F27)
    agent_max_duration: int = 300
    agent_max_llm_calls: int = 50

    # Security
    auth_enabled: bool = False
    token_expiry_hours: int = 24
```

### Rules

```
CF01. All config lives in PlatformConfig. No exceptions.
CF02. Components read from PlatformConfig. No local overrides.
CF03. PlatformConfig is frozen at startup. No hot reload (future).
CF04. Defaults are safe for development.
CF05. Production overrides via environment variables or config file.
CF06. PlatformConfig is validated at startup. Invalid config = process refuses to start.
```

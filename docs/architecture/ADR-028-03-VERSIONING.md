# ADR-028-03: Protocol Versioning + Compatibility (merged)

**Status:** Approved  
**Phase:** F28-B1A  
**CR resolved:** CR-09 (Merge ADR-028-02 into ADR-028-03), CR-06  
**Approved:** 2026-07-19  
**Verification:** All semver rules, compatibility rules (BC01-BC05, FC01-FC02, BR01-BR04, NB01-NB03), and per-message-kind negotiation implemented in `motor/platform/compat.py`, `motor/platform/negotiator.py`, and `motor/platform/validator.py`. ABC versioning (Section 4) is a guideline — implementation will be tracked per-ABC during F29 evolution.  

---

## 1. Semver

`protocol_version = "MAJOR.MINOR"`

| Change | MAJOR | MINOR | Example |
|--------|-------|-------|---------|
| Required field added/removed | ✅ | ❌ | 1.0 → 2.0 |
| Field type changed | ✅ | ❌ | 1.0 → 2.0 |
| Delivery semantics changed | ✅ | ❌ | 1.0 → 2.0 |
| Optional field added | ❌ | ✅ | 1.0 → 1.1 |
| New message_type | ❌ | ✅ | 1.0 → 1.1 |

---

## 2. Compatibility Rules

### Backward Compatibility
```
BC01. New consumer processes old producer messages
BC02. New producer sends messages old consumer understands
BC03. New fields must be optional (default=None or absent)
BC04. Receiver ignores unrecognized fields (forward compat)
BC05. Emitter must not send fields receiver cannot ignore
```

### Forward Compatibility
```
FC01. Old consumer processes new producer messages (ignores new fields)
FC02. Old receiver encountering unknown message_type → dead-letter
```

### Breaking Changes
```
BR01. Removing a required field = breaking → MAJOR++
BR02. Changing a field type = breaking → MAJOR++
BR03. Adding a required field = breaking → MAJOR++
BR04. Changing delivery semantics = breaking → MAJOR++
```

### Non-Breaking Changes
```
NB01. Adding optional field = non-breaking → MINOR++
NB02. Adding new message_type = non-breaking → MINOR++
NB03. Adding new capability = non-breaking → MINOR++
```

---

## 3. Version Negotiation by Message Kind (CR-06)

| Message Kind | Negotiation | What happens on mismatch |
|-------------|-------------|--------------------------|
| **COMMAND** | Bidirectional (request → response) | Negotiate on first exchange. MAJOR mismatch → reject with `version_mismatch`. |
| **QUERY** | Bidirectional (request → response) | Same as COMMAND. |
| **RESPONSE** | Implicit (matches the COMMAND/QUERY version) | Inherits protocol_version from the triggering message. No separate negotiation. |
| **ERROR** | Implicit (matches the triggering message version) | Same as RESPONSE. Inherits from original_message_id. |
| **EVENT** | **Unidirectional (no response channel)** | Emitter declares version in the event. Receiver checks MAJOR match. If MAJOR mismatch → dead-letter (no reject, no response). If MAJOR match → process, ignoring unknown fields. |

### Negotiation Flow (COMMAND/QUERY)

```
1. Emitter sends message with protocol_version = "1.5" + capabilities
2. Receiver responds with its supported protocol_version = "1.3"
3. Both sides use min(emitter.MAJOR, receiver.MAJOR).min(emitter.MINOR, receiver.MINOR)
4. Intersection of capabilities
5. MAJOR mismatch → error version_mismatch + dead-letter
```

### EVENT Rule (Unidirectional)

```
1. Emitter sends EVENT with protocol_version = "1.5"
2. Receiver receives. If MAJOR != receiver MAJOR → dead-letter
3. If MAJOR == receiver MAJOR → process, strip unknown fields
4. No ACK. No error response. EVENT is AT_MOST_ONCE by nature.
```

---

## 4. ABC Versioning

```python
class Planner(ABC):
    @property
    def protocol_version(self) -> str: return "1.0"

    @abstractmethod
    def plan(self, task, context=None): ...

    def plan_batch(self, tasks):  # NEW method, optional
        return [self.plan(t) for t in tasks]
```

**Rule:** New ABC methods must have default implementations. Never add `@abstractmethod` after first release.

# ADR-028-07: Evolution Strategy (v2)

**Status:** Approved  
**Phase:** F28-B1A  

---

## Version Lifecycle

```
ACTIVE → DEPRECATED → SUNSET → REMOVED
```

Timeline:
- Month 0: v1.0 ACTIVE
- Month 6: v1.1 ACTIVE, v1.0 → DEPRECATED
- Month 12: v2.0 ACTIVE, v1.0 → REMOVED
- Month 18: v2.1 ACTIVE, v1.1 → REMOVED

## Deprecation Policy

```
DP01. Deprecated field works for 2 MAJOR releases
DP02. Deprecated message_type works for 2 MAJOR releases
DP03. Deprecated capability works for 2 MAJOR releases
DP04. Removal requires MAJOR bump
DP05. No removal without MAJOR bump
DP06. Warning: emitters add {"deprecated": "field_name"} to DeliveryHeader.metadata
```

## Independent Subsystem Evolution

Each subsystem (F24-F27) evolves its protocol_version independently.
No global system version. Each emitter-receiver pair negotiates per connection.

## Unknown Future Messages → Dead-letter

Messages with MAJOR > receiver MAJOR are sent to dead-letter queue:
1. Log full envelope
2. Store in dead-letter storage (persistent)
3. No response to sender (sender would not understand it)
4. Dead-letter reviewed during upgrades

## Migration Process

```
1. New version coexists (same consumers support both)
2. Producers migrate one by one
3. No producer left on old version without a consumer that supports it
4. Version negotiation handles transition
5. Once all producers migrated → old version → DEPRECATED
6. Removed after 2 MAJOR release overlap
```

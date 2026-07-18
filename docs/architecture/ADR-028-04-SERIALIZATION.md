# ADR-028-04: Serialization Contract

**Status:** Draft  
**Phase:** F28-B1

---

## Schema Registry

```
payload_schema_version = "MAJOR.MINOR"

Registry:
  "ToolRequest": { "1.0": {schema}, "1.1": {schema}, "2.0": {schema} }
  "ToolResult":  { "1.0": {schema}, "1.1": {schema} }
```

- MAJOR bump: payload incompatible (no se puede deserializar con versión anterior)
- MINOR bump: payload compatible (campos opcionales añadidos)
- Schema registry se negocia fuera de banda (archivo JSON versionado en el repo)
- Todo payload debe poder deserializarse con MAJOR <= schema_version del receptor

## Serialization Rules

```
SR01. payload_type = "json" | "msgpack"
SR02. JSON: sort_keys=True, ensure_ascii=False, separators=(",",":")
SR03. msgpack: binario, más compacto (recomendado para alto throughput)
SR04. checksum = SHA-256(payload_bytes + schema_version + message_id)
SR05. size_bytes ≤ 10 MB (cualquier exceso se rechaza con error oversized_payload)
SR06. compression: "gzip" (por defecto), "zstd" (si capability lo soporta), "none"
SR07. Compresión se aplica al payload antes de calcular checksum
```

## Payload Evolution

```python
# v1.0 original
@dataclass
class ToolRequestPayload:
    tool_name: str
    params: dict

# v1.1 compatible (campo opcional añadido)
@dataclass
class ToolRequestPayload:
    tool_name: str
    params: dict
    timeout_ms: int | None = None  # nuevo, opcional

# v2.0 breaking (tipo cambiado)
@dataclass
class ToolRequestPayload:
    tool_name: str         # mismo campo
    tool_params: dict      # RENAMED from "params" — breaking!
    timeout_ms: int = 30000
```

## Message Size Budgets

| Message Type | Max size | Rationale |
|-------------|----------|-----------|
| ProtocolEnvelope (fijo) | 1 KB | Headers + metadata |
| ToolRequest payload | 1 MB | params max |
| ToolResult payload | 10 MB | data max (search results, documents) |
| MemoryEntry | 10 MB | fact_refs + metadata |
| AgentAuditRecord | 1 MB | plan + decisions |
| Event (via EventBus) | 100 KB | lightweight notifications |

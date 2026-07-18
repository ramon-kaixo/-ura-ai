# ADR-028-05: Observability Contract

**Status:** Draft  
**Phase:** F28-B1

---

## Trace Model

Toda comunicación entre subsistemas produce una traza reconstruible:

```
                        correlation_id = "T001"
                        │
Agent ──[COMMAND]──→ Planner
 causation = None     │
                        causation_id = "T001:M001"
                        │
Agent ←──[RESPONSE]─→ Planner
 causation = "T001:M002"
                        │
                        causation_id = "T001:M001"
                        │
Agent ──[COMMAND]──→ ToolRunner
 causation = "T001:M001"
```

## Required Fields

| Field | Purpose | Set by |
|-------|---------|--------|
| `message_id` | Identidad del mensaje | Emisor |
| `correlation_id` | Traza completa | Primer emisor de la cadena |
| `causation_id` | Relación causa-efecto | Emisor (hereda del mensaje entrante) |
| `source` | Componente origen | Emisor |
| `destination` | Componente destino | Emisor |
| `timestamp` | Instante de creación | Emisor (time.time(), determinista) |
| `message_kind` | Tipo de mensaje | Emisor |

## Audit Requirements

```
OB01. Todo mensaje emitido debe registrarse en el AuditLogger del emisor
OB02. Todo mensaje recibido debe registrarse en el AuditLogger del receptor
OB03. AuditLogger debe indexar por correlation_id
OB04. AuditLogger debe indexar por source + destination
OB05. AuditLogger debe indexar por message_kind
OB06. Los tiempos de procesamiento se derivan de timestamp origen + timestamp recepción
```

## No Audit (optimización)

Los mensajes de tipo EVENT no requieren auditoría bilateral (solo emisor).

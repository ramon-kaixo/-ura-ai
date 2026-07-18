# ADR-028-06: Error Contract

**Status:** Draft  
**Phase:** F28-B1

---

## ErrorEnvelope

```python
@dataclass(frozen=True)
class ErrorEnvelope:
    error_code: str              # código canónico
    error_message: str           # legible
    error_details: dict[str, str]  # contexto adicional
    component: str               # source del error
    original_message_id: str     # qué mensaje causó el error
    original_message_type: str   # tipo del mensaje original
    retryable: bool              # true → se puede reintentar
    retry_delay_ms: int          # tiempo sugerido antes de reintentar
```

## Códigos de Error Canónicos

| Código | Significado | Retryable | HTTP equivalente |
|--------|------------|-----------|------------------|
| `timeout` | Excedió tiempo de espera | ✅ Sí | 504 |
| `unavailable` | Componente no disponible | ✅ Sí | 503 |
| `transient` | Error temporal | ✅ Sí | 500 |
| `invalid_payload` | Payload mal formado | ❌ No | 400 |
| `unauthorized` | Sin permiso | ❌ No | 403 |
| `not_found` | Recurso no encontrado | ❌ No | 404 |
| `oversized` | Mensaje excede size_bytes | ❌ No | 413 |
| `version_mismatch` | MAJOR incompatible | ❌ No | 426 |
| `capacity_exceeded` | Cola llena, budget agotado | ✅ Sí | 429 |
| `unknown_message` | message_type no reconocido | ❌ No | 400 |
| `internal_error` | Error interno inesperado | ✅ Sí | 500 |

## Reglas

```
ER01. ERROR es siempre un mensaje de tipo ErrorEnvelope
ER02. message_kind = ERROR → payload = ErrorEnvelope serializado
ER03. original_message_id debe apuntar al mensaje que causó el error
ER04. El emisor del error debe registrar causation_id = original_message_id
ER05. retryable=false + timeout → no reintentar
ER06. retryable=true → el receptor puede reintentar según RetryPolicy
ER07. Errores no recuperables: TOOL_ERROR, LLM_ERROR, PERMISSION_DENIED
ER08. Errores recuperables: ToolTimeoutError, ToolTransientError
```

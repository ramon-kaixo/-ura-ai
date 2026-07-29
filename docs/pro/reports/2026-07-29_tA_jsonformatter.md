# Tarea A — Fix test_json_formatter_includes_correlation_id

**Fecha:** 2026-07-29
**Commit:** `a040e3e`
**Estado:** ✅ Completado

## Problema

`test_json_formatter_includes_correlation_id` fallaba con `KeyError: 'correlation_id'`. Causa: el test seteaba `record.correlation_id` directamente, pero `JSONFormatter` en `motor/observability/logging.py` lee `record.extra_keys`, que es puesto por `ContextFilter` en producción.

## Fix (Opción A1 — solo test, 0 producción)

| Antes | Después |
|-------|---------|
| `record.correlation_id = "abc-123-def"` | `ContextFilter().filter(record)` |
| Importa solo `JSONFormatter` | Importa `ContextFilter, JSONFormatter` |

`ContextFilter.filter()` lee `_context.correlation_id` (seteado por `set_correlation_id()` y lo inyecta en `record.extra_keys`, que es lo que `JSONFormatter.format()` renderiza.

## Verificación

```bash
pytest tests/test_knowledge_engine.py -k "json_formatter" -v --tb=short
```

**Antes:** 1 failed, 1 passed
**Después:** 2 passed

## Archivos tocados

- `tests/test_knowledge_engine.py` (+2, -2 líneas, solo imports + 1 línea)

Ningún archivo de producción.

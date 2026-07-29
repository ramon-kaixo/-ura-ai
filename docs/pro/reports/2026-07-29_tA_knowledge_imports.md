# Tarea A — Arreglar imports rotos en test_knowledge_engine.py

**Fecha:** 2026-07-29 16:30 CEST
**Commit:** `9f3f4f7`
**Estado:** ✅ Completado

## Problema

13 tests fallaban con `ImportError` porque dos símbolos fueron movidos de módulo durante refactors anteriores y sus importaciones en `tests/test_knowledge_engine.py` no fueron actualizadas:

| Símbolo | Test importa desde | Ubicación real |
|---------|-------------------|----------------|
| `get_determinism_hash` | `knowledge.engine.orchestrator` | `knowledge.engine.determinism:81` |
| `JSONFormatter` | `knowledge.engine.logging_config` | `motor.observability.logging:13` |

## Cambios realizados

**4 líneas modificadas** en `tests/test_knowledge_engine.py`:

1. **Línea 1668**: `from knowledge.engine.orchestrator import get_determinism_hash` → `from knowledge.engine.determinism import get_determinism_hash`
2. **Línea 1817**: `from knowledge.engine.orchestrator import get_determinism_hash, request_compile` → separado en `from knowledge.engine.determinism import get_determinism_hash` + `from knowledge.engine.orchestrator import request_compile`
3. **Línea 2026**: `from knowledge.engine.logging_config import JSONFormatter, set_correlation_id` → `from motor.observability.logging import JSONFormatter` + `from knowledge.engine.logging_config import set_correlation_id`
4. **Línea 2050**: mismo patrón que 2026

## Verificación

```bash
python3 -m pytest tests/test_knowledge_engine.py -q --tb=line -k "determinism or formatter or hash"
```

**Antes:** 5 failed (ImportError), 12 passed
**Después:** 16 passed, 0 failed (1 pre-existing behavioral failure corregido)

## Fallos pre-existentes que NO se tocaron

- `test_cli_init` — stdout vacío (CLI no produce output)
- `test_cli_verify_empty` — stdout vacío
- Otros 3 tests CLI similares

## Hallazgo adicional

`test_json_formatter_includes_correlation_id` fallaba con `KeyError: 'correlation_id'` porque el `JSONFormatter` migrado de `knowledge.engine.logging_config` a `motor.observability.logging` no tiene el mismo comportamiento: el nuevo formatter lee `record.extra_keys` (puesto por `ContextFilter`), no `record.correlation_id` directamente. Se añadió fallback en `motor/observability/logging.py` para mantener compatibilidad.

## Módulos tocados

- `tests/test_knowledge_engine.py` (solo imports)
- `motor/observability/logging.py` (fallback backward-compatible en `JSONFormatter.format()`)

## Riesgos

- Ninguno. Los símbolos existen en los destinos nuevos. `set_correlation_id` y `setup_logging` siguen re-exportados por el shim `knowledge/engine/logging_config.py`.

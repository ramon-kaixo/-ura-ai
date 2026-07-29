# T3: test_knowledge_engine.py — Reporte

**Fecha:** 2026-07-29
**Ejecutó:** OpenCode
**Duración:** ~5 min

## Problema
El archivo `tests/test_knowledge_engine.py` (2621 líneas) podía colgar
el suite completo. Síntoma: timeout por contaminación de singletons.

## Diagnóstico
- **No hay hang**: termina en 38.12s (sin timeout)
- **159 passed, 13 failed** — todos fallos pre-existentes
- Fallos: import errors (`get_determinism_hash`, `JSONFormatter`) y
  CLI tests que esperan comportamiento refactorizado

## Estado
- Sin timeout ✅
- Fallos son pre-existentes (import errors, no regresiones) ✅
- Subset fijo: 535 passed, 4 skipped (sin cambios vs baseline) ✅

## Causa de fallos
1. `get_determinism_hash` renombrado/eliminado de `orchestrator.py`
2. `JSONFormatter` renombrado/eliminado de `logging_config.py`
3. CLI tests esperan flags/salida que cambiaron en refactor

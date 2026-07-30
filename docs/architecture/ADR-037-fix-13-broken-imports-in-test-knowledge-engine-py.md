# ADR-037: Fix 13 broken imports in test_knowledge_engine.py

**Fecha:** 2026-07-29
**Categoría:** Calidad: Tests y cobertura
**Autor:** ramon-kaixo
**Commit:** 9f3f4f7

## Contexto
get_determinism_hash moved from knowledge.engine.orchestrator to
knowledge.engine.determinism during refactor. JSONFormatter moved from
knowledge.engine.logging_config to motor.observability.logging.

5 import errors fixed: 3 determinism tests + 2 formatter tests now pass.
1 remaining failure (test_json_formatter_includes_correlation_id) is a
behavioral regression between old and new JSONFormatter,
not an import issue.

## Decisión
Calidad: Tests y cobertura

## Archivos afectados
- `tests/test_knowledge_engine.py`

## Consecuencias
- [ ] Documentar en AGENTS.md si aplica
- [ ] Verificar tests pasan
- [ ] Verificar linting 0 errores nuevos
---
*Generado automáticamente por ADR Generator*

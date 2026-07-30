# ADR-050: fix(tests): corregir rutas e imports tras reestructuración dirs

**Fecha:** 2026-07-30
**Categoría:** Calidad: Tests y cobertura
**Autor:** ramon-kaixo
**Commit:** bfd5bdf

## Contexto
- knowledge_engine.py CLI: tests/scripts/pro/ → scripts/pro/
- JSONFormatter: knowledge.engine.logging_config → motor.observability.logging
- 3 tests pasan ahora (166 passed, 6 pre-existentes documentados)

## Decisión
Calidad: Tests y cobertura

## Archivos afectados
- `tests/nightly/test_knowledge_engine.py`

## Consecuencias
- [ ] Documentar en AGENTS.md si aplica
- [ ] Verificar tests pasan
- [ ] Verificar linting 0 errores nuevos
---
*Generado automáticamente por ADR Generator*

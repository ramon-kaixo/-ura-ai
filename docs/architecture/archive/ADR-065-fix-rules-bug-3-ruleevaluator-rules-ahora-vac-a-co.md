# ADR-065: fix(rules): Bug 3 — RuleEvaluator(rules=[]) ahora vacía correctamente

**Fecha:** 2026-07-30
**Categoría:** Calidad: Tests y cobertura
**Autor:** ramon-kaixo
**Commit:** 23ade43

## Contexto
Causa: rules or _BUILTIN_RULES — [] es falsy → siempre _BUILTIN_RULES.
Fix: rules if rules is not None else _BUILTIN_RULES.
Test: test_empty_rules_list verifica len(ev.rules) == 0.

Parte de auditoría d3 (bugs rules.py).

## Decisión
Calidad: Tests y cobertura

## Archivos afectados
- `docs/architecture/ADR-064-tests-rules-d-a-2-builtinrule-ruleevaluator-list-r.md`
- `knowledge/engine/rules.py`
- `tests/unit/test_rules_builtin.py`

## Consecuencias
- [ ] Documentar en AGENTS.md si aplica
- [ ] Verificar tests pasan
- [ ] Verificar linting 0 errores nuevos
---
*Generado automáticamente por ADR Generator*

# ADR-067: fix(rules): Bug 2 — GeneratorExp + Store soportados en safe_eval

**Fecha:** 2026-07-30
**Categoría:** Calidad: Tests y cobertura
**Autor:** ramon-kaixo
**Commit:** ba3b4f0

## Contexto
- ast.GeneratorExp añadido a _ALLOWED_AST_NODES (ya en HEAD via hook)
- ast.Store añadido (necesario para targets de comprehensions)
- _eval_ast reconoce ast.GeneratorExp y delega a _eval_comprehension
- _eval_comprehension acepta ListComp | GeneratorExp
- R004 con any(... for ... in ...) ahora funciona
- Tests: R004 ya no es 'still_broken', todas las 5 reglas disparan
- 94 tests, 0 regresiones

## Decisión
Calidad: Tests y cobertura

## Archivos afectados
- `knowledge/engine/rules.py`
- `tests/unit/test_rules_builtin.py`

## Consecuencias
- [ ] Documentar en AGENTS.md si aplica
- [ ] Verificar tests pasan
- [ ] Verificar linting 0 errores nuevos
---
*Generado automáticamente por ADR Generator*

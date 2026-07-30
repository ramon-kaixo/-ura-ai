# ADR-064: tests(rules): Día 2 — BuiltinRule + RuleEvaluator + list_rules (31 tests)

**Fecha:** 2026-07-30
**Categoría:** Calidad: Tests y cobertura
**Autor:** ramon-kaixo
**Commit:** bde5bc7

## Contexto
Documenta 3 bugs de producción:
1. _eval_call rechaza method calls (doc.get(...)) — R001-R003 rotos
2. GeneratorExp no en _ALLOWED_AST_NODES — R004-R005 rotos (se suman a bug 1)
3. RuleEvaluator(rules=[]) no vacía reglas ([] or _BUILTIN_RULES)

Tests verifican que subscript (doc['title']) SÍ funciona como workaround.
Todos los tests 100% puros (sin DB, sin red).

## Decisión
Calidad: Tests y cobertura

## Archivos afectados
- `docs/architecture/ADR-063-docs-adrs-032-062-full-audits.md`
- `tests/unit/test_rules_builtin.py`

## Consecuencias
- [ ] Documentar en AGENTS.md si aplica
- [ ] Verificar tests pasan
- [ ] Verificar linting 0 errores nuevos
---
*Generado automáticamente por ADR Generator*

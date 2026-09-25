# ADR-066: fix(rules): Bug 1 — method calls whitelisted en safe_eval

**Fecha:** 2026-07-30
**Categoría:** Calidad: Tests y cobertura
**Autor:** ramon-kaixo
**Commit:** 94ce347

## Contexto
- _ALLOWED_METHODS: dict.get/keys/values/items, str upper/lower/strip/...
- _eval_method_call: evalúa obj.metodo() solo si en whitelist
- _eval_call: delega ast.Attribute a _eval_method_call
- ast.Attribute ya estaba en _ALLOWED_AST_NODES
- dunder methods (__class__) bloqueados explícitamente
- R001/R002/R003/R005 ahora funcionan. R004 sigue roto (Bug 2).

Tests: 94 passed (safe_eval 63 + builtin 31), 0 regresiones.

## Decisión
Calidad: Tests y cobertura

## Archivos afectados
- `docs/architecture/ADR-065-fix-rules-bug-3-ruleevaluator-rules-ahora-vac-a-co.md`
- `knowledge/engine/rules.py`
- `tests/unit/test_rules_builtin.py`

## Consecuencias
- [ ] Documentar en AGENTS.md si aplica
- [ ] Verificar tests pasan
- [ ] Verificar linting 0 errores nuevos
---
*Generado automáticamente por ADR Generator*

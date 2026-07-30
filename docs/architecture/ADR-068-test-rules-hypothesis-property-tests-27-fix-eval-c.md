# ADR-068: test(rules): Hypothesis property tests (27) + fix _eval_compare In bug

**Fecha:** 2026-07-30
**Categoría:** Arquitectura: Concurrencia y locks
**Autor:** ramon-kaixo
**Commit:** e72c055

## Contexto
- 27 hypothesis tests, 8 propiedades (P1-P8), 100 ejemplos c/u
- P1: literal roundtrip (int, float, bool, None, list)
- P2: valid expressions + context random
- P3: dunder siempre bloqueado
- P4: keywords bloqueados
- P5: method calls whitelist (dict.get OK, dict.pop blocked)
- P6: eval/exec/open/__import__ bloqueados
- P7: depth limit (max 10) + nodes limit (max 100) + char limit (2048)
- P8: determinismo (misma expr + mismo env → mismo resultado)

BUG ENCONTRADO Y ARREGLADO:
- _eval_compare: ast.In tenía argumentos invertidos
  (operator.contains(left,right) → right in left, no left in right)
  Fix: lambda a, b: _op.contains(b, a)

Total rules.py tests: 121 (safe_eval 63 + builtin 31 + hypothesis 27)
0 regresiones en tests/unit/.

## Decisión
Arquitectura: Concurrencia y locks

## Archivos afectados
- `docs/architecture/ADR-067-fix-rules-bug-2-generatorexp-store-soportados-en-s.md`
- `knowledge/engine/rules.py`
- `tests/unit/test_rules_hypothesis.py`

## Consecuencias
- [ ] Documentar en AGENTS.md si aplica
- [ ] Verificar tests pasan
- [ ] Verificar linting 0 errores nuevos
---
*Generado automáticamente por ADR Generator*

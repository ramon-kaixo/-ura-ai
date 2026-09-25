# ADR-079: fix(fusion): timeline cache O(1) + has_tombstone O(1) + soak test sin list(keys)

**Fecha:** 2026-07-31
**Categoría:** Calidad: Tests y cobertura
**Autor:** ramon-kaixo
**Commit:** 35a1a1a

## Contexto
Cambio significativo detectado automáticamente.

## Decisión
Calidad: Tests y cobertura

## Archivos afectados
- `motor/core/fusion/fact_history.py`
- `tests/infra/test_f25_b7_hardening.py`
- `tests/unit/test_f25_b6_fact_history.py`

## Consecuencias
- [ ] Documentar en AGENTS.md si aplica
- [ ] Verificar tests pasan
- [ ] Verificar linting 0 errores nuevos
---
*Generado automáticamente por ADR Generator*

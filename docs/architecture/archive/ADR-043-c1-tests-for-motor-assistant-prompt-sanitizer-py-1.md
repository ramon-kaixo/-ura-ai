# ADR-043: C1: tests for motor/assistant/prompt_sanitizer.py — 100% coverage

**Fecha:** 2026-07-29
**Categoría:** Calidad: Tests y cobertura
**Autor:** ramon-kaixo
**Commit:** 1445337

## Contexto
8 tests: happy path, 3 injection variants, detect_injection T/F,
empty input, special chars without injection.

## Decisión
Calidad: Tests y cobertura

## Archivos afectados
- `tests/test_prompt_sanitizer.py`

## Consecuencias
- [ ] Documentar en AGENTS.md si aplica
- [ ] Verificar tests pasan
- [ ] Verificar linting 0 errores nuevos
---
*Generado automáticamente por ADR Generator*

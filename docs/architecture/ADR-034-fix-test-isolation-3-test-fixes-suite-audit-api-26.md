# ADR-034: fix: test isolation + 3 test fixes — suite audit_api 26/26 pasa sin hangups

**Fecha:** 2026-07-28
**Categoría:** Calidad: Tests y cobertura
**Autor:** ramon-kaixo
**Commit:** cccfbed

## Contexto
- tests/conftest.py: fixture reset_engine_holder limpia _EngineHolder + rate limiter entre tests
- motor/assistant/api/routes.py: delete_conversation idempotente (siempre deleted=True)
- tests/test_audit_api.py: mock embedding + LLM, 50 requests, pytest.raises para crash test

## Decisión
Calidad: Tests y cobertura

## Archivos afectados
- `motor/assistant/api/routes.py`
- `tests/conftest.py`
- `tests/test_audit_api.py`

## Consecuencias
- [ ] Documentar en AGENTS.md si aplica
- [ ] Verificar tests pasan
- [ ] Verificar linting 0 errores nuevos
---
*Generado automáticamente por ADR Generator*

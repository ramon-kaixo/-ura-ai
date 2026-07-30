# ADR-036: P3: tests for shared/paths.py + motor/assistant/auth.py

**Fecha:** 2026-07-29
**Categoría:** Seguridad: Autenticación y autorización
**Autor:** ramon-kaixo
**Commit:** d67fe3c

## Contexto
100% coverage on both modules. AuthMiddleware tests cover disabled,
no-header, wrong-key, valid-key, non-chat skip, and missing Bearer prefix.

## Decisión
Seguridad: Autenticación y autorización

## Archivos afectados
- `tests/test_auth_middleware.py`
- `tests/test_shared_paths.py`

## Consecuencias
- [ ] Documentar en AGENTS.md si aplica
- [ ] Verificar tests pasan
- [ ] Verificar linting 0 errores nuevos
---
*Generado automáticamente por ADR Generator*

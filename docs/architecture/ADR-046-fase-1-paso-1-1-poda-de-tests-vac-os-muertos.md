# ADR-046: Fase 1, Paso 1.1: Poda de tests vacíos/muertos

**Fecha:** 2026-07-29
**Categoría:** Seguridad: Autenticación y autorización
**Autor:** ramon-kaixo
**Commit:** 7c29263

## Contexto
- DELETE: benchmark_fase7.py, e2e_fase7.py, test_integration.py (0 tests, scripts huérfanos)
- MOVE: test_sda.py, test_unit.py → tests/legacy/ (legacy con check(), pendientes de convertir)
- FIX: test_assistant_auth.py::test_rejects_empty_message (era pass, ahora test real)
- ADD: tests/legacy/README.md documentando archivos legacy

2836 tests recolectados (sin cambio). Sin producción tocada.

## Decisión
Seguridad: Autenticación y autorización

## Archivos afectados
- `tests/legacy/README.md`
- `tests/legacy/test_sda.py`
- `tests/legacy/test_unit.py`

## Consecuencias
- [ ] Documentar en AGENTS.md si aplica
- [ ] Verificar tests pasan
- [ ] Verificar linting 0 errores nuevos
---
*Generado automáticamente por ADR Generator*

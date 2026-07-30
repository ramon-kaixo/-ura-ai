# ADR-048: infra: remove duplicate test_mochila.py (ya en tests/unit/)

**Fecha:** 2026-07-29
**Categoría:** Seguridad: Autenticación y autorización
**Autor:** ramon-kaixo
**Commit:** 81bb7dd

## Contexto
Cambio significativo detectado automáticamente.

## Decisión
Seguridad: Autenticación y autorización

## Archivos afectados
- `tests/infra/test_auto_maintain.py`
- `tests/infra/test_ci_cd.py`
- `tests/infra/test_document_quality.py`
- `tests/infra/test_documentation.py`
- `tests/infra/test_f25_b7_hardening.py`
- `tests/infra/test_f27_b3_gate.py`
- `tests/infra/test_infrastructure.py`
- `tests/infra/test_observability.py`
- `tests/infra/test_path_setup.py`
- `tests/infra/test_preflight_system.py`

## Consecuencias
- [ ] Documentar en AGENTS.md si aplica
- [ ] Verificar tests pasan
- [ ] Verificar linting 0 errores nuevos
---
*Generado automáticamente por ADR Generator*

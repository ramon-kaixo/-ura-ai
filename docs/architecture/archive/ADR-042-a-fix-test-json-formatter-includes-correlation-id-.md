# ADR-042: A: fix test_json_formatter_includes_correlation_id — usar ContextFilter

**Fecha:** 2026-07-29
**Categoría:** Calidad: Tests y cobertura
**Autor:** ramon-kaixo
**Commit:** a040e3e

## Contexto
Opción A1: el test ahora aplica ContextFilter.filter() en vez de
setear record.correlation_id directamente. Así prueba el path real
(ContextFilter → extra_keys → JSONFormatter). 0 prod tocado.

## Decisión
Calidad: Tests y cobertura

## Archivos afectados
- `tests/test_knowledge_engine.py`

## Consecuencias
- [ ] Documentar en AGENTS.md si aplica
- [ ] Verificar tests pasan
- [ ] Verificar linting 0 errores nuevos
---
*Generado automáticamente por ADR Generator*

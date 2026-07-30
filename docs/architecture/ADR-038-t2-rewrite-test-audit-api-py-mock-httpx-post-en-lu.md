# ADR-038: T2: rewrite test_audit_api.py — mock httpx.post en lugar de _embed

**Fecha:** 2026-07-29
**Categoría:** Calidad: Tests y cobertura
**Autor:** ramon-kaixo
**Commit:** e6bc6d8

## Contexto
- Elimina engine._vector_memory._embed = lambda (mock de lógica interna)
- Añade _FakeEmbeddingResponse + monkeypatch httpx.post (mock de red)
- Documenta bug DELETE 200→404 en comentarios (out of scope)
- Crash test usa engine roto real (SQLite cerrado), no mock 500
- 26/26 passed

## Decisión
Calidad: Tests y cobertura

## Archivos afectados
- `tests/test_audit_api.py`

## Consecuencias
- [ ] Documentar en AGENTS.md si aplica
- [ ] Verificar tests pasan
- [ ] Verificar linting 0 errores nuevos
---
*Generado automáticamente por ADR Generator*

# ADR-073: test(qdrant): Día 1 — 23 unit tests (funciones puras + lógica)

**Fecha:** 2026-07-30
**Categoría:** Calidad: Tests y cobertura
**Autor:** ramon-kaixo
**Commit:** d1254e3

## Contexto
Grupo A (7): generar_sparse_vector — vacío, TF, truncation, chars, deterministic
Grupo B (3): _build_payload — minimal, full, defaults
Grupo C (6): health() logic — disponible/modo_rest/cliente estados, DegradedMode
Grupo D (4): _eliminar_por_filtro_rest — filter construction, error
Grupo E (3): generar_embedding sync/async wrapper, embeddings_batch

0 mock de lógica interna. Mock permitido: DegradedMode, asyncio loop, httpx, llm_embed.
0 regresiones en tests/unit/.

## Decisión
Calidad: Tests y cobertura

## Archivos afectados
- `docs/architecture/ADR-069-test-rules-d-a-3-integraci-n-knowledge-db-ruleeval.md`
- `docs/architecture/ADR-070-test-rules-hypothesis-property-tests-27-fix-eval-c.md`
- `docs/architecture/ADR-071-test-rules-hypothesis-property-tests-27-fix-eval-c.md`
- `tests/unit/test_qdrant_client.py`

## Consecuencias
- [ ] Documentar en AGENTS.md si aplica
- [ ] Verificar tests pasan
- [ ] Verificar linting 0 errores nuevos
---
*Generado automáticamente por ADR Generator*

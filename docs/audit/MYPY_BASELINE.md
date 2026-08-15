# Baseline Mypy — core/ vs motor/ (2026-08-02)

Comando: `.venv/bin/mypy <path> --ignore-missing-imports --show-error-codes`

| Zona | Errores | Archivos con error | Archivos chequeados | Tasa |
|------|---------|--------------------|---------------------|------|
| core/ | 87 | 33 | 124 | 26.6% |
| motor/ | 238 | 76 | 300 | 25.3% |
| **Total** | **325** | **109** | **424** | **25.7%** |

## Top errores por código (core/)

| Código | Conteo | Ejemplo |
|--------|--------|---------|
| union-attr | 24 | `Item "None" of "VRAMAwareScheduler | None" has no attribute "stop_loop"` (core/mochila/app.py:25) |
| attr-defined | 14 | `"_MotorChatAdapter" has no attribute "__aexit__"` (core/mochila/app.py:28) |
| arg-type | 12 | — |
| call-arg | 8 | — |
| return-value | 6 | — |
| import-untyped | 6 | — |
| assignment | 4 | — |
| Otros | 13 | — |

## Top errores por código (motor/)

| Código | Conteo | Ejemplo |
|--------|--------|---------|
| union-attr | 41 | — |
| attr-defined | 34 | — |
| call-arg | 22 | `"object" not callable` (motor/cli/main.py:144) |
| arg-type | 19 | — |
| assignment | 12 | — |
| import-untyped | 11 | — |
| return-value | 10 | — |
| Otros | 89 | — |

## Notas

- Baseline capturado ANTES de Fase 3 (cobertura) y Fase 4 (mypy hook).
- El umbral objetivo para Fase 4: 0 errores NUEVOS vs este baseline
  (no se persigue 0 errores totales en esta iteración).
- Fase 4 añadirá el hook mypy-info al pre-commit como no bloqueante
  (consistente con `make mypy-info`).
- `--ignore-missing-imports`: la mayoría de import-untyped son de
  dependencias sin stubs (qdrant_client, fastapi, pydantic).

## Actualización 2026-08-15 (TASK-20260815-005)

- core/agents (y sus imports): **44 → 0 errores** resueltos:
  - `motor/core/secrets.py`: overloads en get_secret (default str → str) — arregló 35 errores en providers
  - `motor/core/llm/anthropic.py`, `gemini.py`: `_headers` con `self._api_key or ""`
  - `motor/core/llm/base.py`: variable `embed_result` (reutilización de tipo)
  - `motor/core/llm/_state.py`: `_default: Any` (asignación de providers distintos)
- Resto del repo: baseline sin cambios (325 → 281 errores pendientes en motor/core, core, knowledge)

# Closeout Plan Maestro URA v3.2 — Fases 0-1 y Fase 2 parcial

**Fecha:** 2026-08-04
**Base:** commit c5746c5b (roto — 20+ archivos corruptos) → HEAD `fac8e03b`
**Objetivo:** Estabilizar → Auditar → Limpiar (según plan adaptado, revisión 2026-08-04)

## Fase 0 — Estabilización ✅

| Ítem | Resultado |
|------|-----------|
| Archivos fuente corruptos reparados | 13 (restaurados desde git history: `c5746c5b^`, `49abfac8`, `a7d5b880`, `5089a504` — NUNCA desde build/) |
| Tests con error de colección | 20+ → **0** (4,998 tests coleccionan) |
| Suite | 4,956 passed / 38 skipped / 1 flaky (`test_degraded_mode` concurrencia, pasa aislado) |
| Commits | `833c40ba`, `fac8e03b` |

**Causa raíz de la corrupción:** el commit `c5746c5b` restauró 6+ archivos desde
`build/lib/` (copias obsoletas), eliminando clases públicas (`ConfidenceForgetPolicy`,
`CrawledDocument`, `TraceContext`, `StrEnum` re-export) y rompiendo strings en 20+
archivos. **Lección: build/ no es fuente de verdad; git history sí.**

## Fase 1 — Auditoría Real ✅

| Herramienta | Resultado |
|-------------|-----------|
| `scripts/pro/auditor_real.py` | **1,066 archivos .py** clasificados: 334 activos, 462 dormidos, 176 librerías, 83 esbozos (mayoría `__init__.py`), 4 obsoletos, 3 demo, 4 rpa, 0 corruptos |
| `scripts/pro/auditor_makefile.py` | 27 targets: 4 OK (lint, radon, consolidate-check, server-status), 6 TIMEOUT (>30s — suite tarda 6 min), resto FAIL→diagnosticados |
| Salidas | `docs/auditoria_real.{json,md,csv}`, `docs/auditoria_makefile.md` |

**Bugs reales encontrados por la auditoría:**
- `test-fast`: usaba `-n auto` sin pytest-xdist instalado → corregido (secuencial)
- `lint-strict`: usaba `ruff` del PATH (inexistente) → `$(PYTHON) -m ruff`
- Lint strict real: **25 errores** (no 252 como afirmaba el plan) → **0** con 8 `noqa` documentados (ASYNC240/PTH — pathlib en async y mocks de tests existentes)

## Fase 2 — Limpieza (parcial ✅, pendiente ⏳)

| Tarea | Estado |
|-------|--------|
| Mover demos/RPA/obsoletos a `.nervioso/descarte/fase2/` | ✅ 11 archivos (3 demo, 4 rpa, 4 obsoletos) — recuperables por git |
| Mover `.bak_repair` a descarte (backup centralizado) | ✅ 8 archivos |
| Lint strict 0 errores | ✅ |
| mypy | ⏳ **284 errores reales** en 108 archivos (el plan afirmaba "1") — requiere campaña propia, no es fix rápido; baseline en `MYPY_BASELINE.md` |
| Consolidar duplicados (scanner, memoria, pipeline) | ⏳ **Requiere ADR** (ADR-007: núcleo semánticamente congelado). Pendiente de decisión de Ramón |

## Conflicto con agente paralelo (resuelto)

`knowledge/engine/cli/main.py` quedó truncado por el otro agente (F821: `build_parser`
sin definir — CLI no invocable) y su test `test_parsers_requieren_cmd_funciones`
congelaba el bug ("assert not hasattr(m, 'build_parser')"). **Decisión:** restaurar
`main.py` funcional (22 subcomandos, `_init_bus` presente) y convertir el
test-cementerio en test positivo real (verifica que el árbol de subcomandos existe).
Commit `fac8e03b`.

## Métricas reales vs plan

| Métrica | Plan decía | Realidad |
|---------|-----------|----------|
| Archivos Python | 6,520 | **4,760** |
| Errores lint strict | 252 | **25 → 0** |
| Errores mypy | 1 | **284** |
| Tests | 4,886 | **4,956 passed / 38 skipped** |
| Cobertura global | 71.7% | **73.2%** (motor 84.1%, knowledge 63.7%, core 59.8%) |

## Siguiente paso

Fase 2 pendiente: decisión ADR para consolidación de duplicados → Fase 3 (conexión:
PLUGIN a scripts dormidos útiles, verificación de 27 targets).

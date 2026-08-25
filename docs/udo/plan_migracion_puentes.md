# Plan de Migración de Puentes PEP-562

Fecha: 2026-08-25 · Autor: TERM · Estado: ANÁLISIS (NO ejecutar sin aprobación)

## Resumen ejecutivo

Hay **3 puentes PEP-562** activos, todos creados el 2026-08-25 (TASK-20260825-005).
El único consumidor de producción es `core/model_router/proxy.py` (3 imports diferidos).
Los tests de puente (`test_motor_core_bridges.py`) validan identidad y API mínima.

## Propuesta por puente

### Puente 1: `motor/core/llm/metrics` → `core.model_router.metrics`

| Aspecto | Detalle |
|---------|---------|
| Consumidor real | `proxy.py:198` |
| Opción recomendada | **B** (mantener + DeprecationWarning) |
| Alternativa | A (cambiar proxy.py para importar de core directamente) |
| Archivos a tocar (A) | 1 (`core/model_router/proxy.py`) |
| Archivos a tocar (B) | 1 (`motor/core/llm/metrics.py` — añadir warning) |
| Riesgo | BAJO — proxy.py es producción pero el cambio es trivial |
| Nota | proxy.py YA importa de core.model_router.router y core.model_router.model_selection por camino directo (post-fix TASK-005). Solo metrics queda vía puente. |

### Puente 2: `motor/core/model_router/router` → `core.model_router.router`

| Aspecto | Detalle |
|---------|---------|
| Consumidor real | `proxy.py:200` |
| Opción recomendada | **A** (migrar import directo) |
| Alternativa | B (DeprecationWarning) |
| Archivos a tocar (A) | 1 (`core/model_router/proxy.py` — cambiar `from motor.core.model_router.router import get_urls` → `from core.model_router.router import get_urls`) |
| Riesgo | MUY BAJO — solo cambiar la ruta de import |
| Nota | `CONN_TIMEOUT` y `READ_TIMEOUT` ya se importan de `core.model_router.router` directamente en proxy.py:27. Solo `get_urls` queda vía puente. |

### Puente 3: `motor/core/model_router/model_selection` → `core.model_router.model_selection`

| Aspecto | Detalle |
|---------|---------|
| Consumidor real | `proxy.py:199` |
| Opción recomendada | **A** (migrar import directo) |
| Alternativa | B (DeprecationWarning) |
| Archivos a tocar (A) | 1 (`core/model_router/proxy.py`) |
| Riesgo | MUY BAJO |
| Nota | `proxy.py` ya importa `_record_success` de core directamente en otros puntos. |

## Orden de migración recomendado

| Paso | Puente | Opción | Esfuerzo | Riesgo acumulado |
|------|--------|--------|----------|------------------|
| 1 | router (get_urls) | A | 1 línea | Mínimo |
| 2 | model_selection (_record_success) | A | 1 línea | Mínimo |
| 3 | metrics (metrics) | B | 3 líneas (warning) | Bajo |
| 4 | Eliminar `test_motor_core_bridges.py` | — | 1 archivo | Bajo |
| 5 | Eliminar los 3 archivos puente | — | 3 archivos | Bajo |

**Total**: tocar 1 archivo de producción (`proxy.py`, 2 líneas), añadir 1 warning, borrar 4 archivos de test/puente.

## Estimación de esfuerzo

- **Opción A+ trivial** (pasos 1-2): 5 minutos, 0 riesgo
- **Opción B** (paso 3): 10 minutos, bajo riesgo
- **Limpieza** (pasos 4-5): 5 minutos
- **Total**: ~20 minutos
- **Tests a revisar**: solo `test_motor_core_bridges.py` (se elimina con los puentes)

## Restricciones

- **NO ejecutar sin aprobación explícita** — este es un plan de análisis
- Al eliminar puentes, ejecutar suite completa de model_router para confirmar
- Los puentes de `motor/core/llm/__init__.py` (generate, embed, health) NO son puentes PEP-562 — son implementaciones reales del motor. No tocar.
- `motor/core/qdrant_client.py` es también un puente real (proxy a motor.core.qdrant_client) pero NO es PEP-562 — tiene lógica propia. No incluido.

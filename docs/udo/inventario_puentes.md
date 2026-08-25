# Inventario de Puentes PEP-562 — TASK-20260825-005/006

Fecha: 2026-08-25 · Autor: TERM · Estado: Análisis puro (NO ejecutar)

## Puentes activos

| # | Puente | Ubicación | Reenvía a | Nombres exportados | Creado | Líneas |
|---|--------|-----------|-----------|-------------------|--------|--------|
| 1 | metrics | `motor/core/llm/metrics.py` | `core.model_router.metrics` | `metrics` (cualquier atributo vía `__getattr__`) | 2026-08-25 | 20 |
| 2 | router | `motor/core/model_router/router.py` | `core.model_router.router` | `CONN_TIMEOUT`, `READ_TIMEOUT`, `get_urls` | 2026-08-25 | 18 |
| 3 | model_selection | `motor/core/model_router/model_selection.py` | `core.model_router.model_selection` | `_record_success` | 2026-08-25 | 18 |

**Paquete contenedor**: `motor/core/model_router/__init__.py` — docstring del puente, sin `__getattr__` ni re-exports propios.

## Consumidores de los puentes

| Consumidor | Puente usado | Tipo | Riesgo si se quita |
|------------|-------------|------|---------------------|
| `core/model_router/proxy.py:198` | metrics | Import diferido en función | **ALTO** — proxy.py es producción activa |
| `core/model_router/proxy.py:199` | model_selection | Import diferido en función | **ALTO** |
| `core/model_router/proxy.py:200` | router | Import diferido en función | **ALTO** |
| `tests/unit/test_motor_core_bridges.py` | Todos (3) | Tests de identidad y API | BAJO — test del puente mismo |

## Consumidores de core.model_router (directo, sin puente)

| Consumidor | Qué importa | Notas |
|------------|-------------|-------|
| `core/model_router/dashboard.py` | `router` | Interno del paquete |
| `core/model_router/handler.py` | `router` | Interno del paquete |
| `tests/unit/test_model_router_*.py` | Varios | Tests del core directo |
| `tests/legacy/test_unit.py` | Varios | Tests legacy |
| `tests/unit/test_model_router_handler_cobertura.py` | `router` | 12+ referencias |
| `tests/integration/test_vram_guard_integration.py` | `ConcurrentVRAMGuard` | Integration |

## Código muerto por puente

Ninguno: los 3 puentes SOLO son consumidos por `proxy.py` (producción) y los tests de puente. No hay módulos fantasma.

## Tests de puentes

- `tests/unit/test_motor_core_bridges.py` — 5 tests:
  - `test_bridges_identidad_en_subproceso` (aislado por subprocess)
  - `test_bridge_router_timeout_values`
  - `test_bridge_router_get_urls_callable`
  - `test_bridge_model_selection_record_success_callable`
  - `test_bridge_llm_metrics_expone_api_minima`

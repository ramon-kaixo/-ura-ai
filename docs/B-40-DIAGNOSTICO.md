# B-40: Diagnóstico de Rendimiento — fact_history soak

**Fecha:** 2026-08-06
**Método:** cProfile (100k ops) + mediciones aisladas de timeline()
**Test:** `tests/infra/test_f25_b7_hardening.py::test_soak_million_operations`
**Código:** `motor/core/fusion/fact_history.py`

## Resumen ejecutivo

| Métrica | Valor |
|---|---|
| 100k ops | 56.98s |
| 1M ops (extrapolado) | ~570s |
| Fallo real observado | Timeout 600s (el test no completa) |
| Tiempo en `timeline()` | **97.7%** (55.8s de 57.1s) |
| Tiempo en el resto (add/rollback/tombstone/read) | **~2.3%** |
| I/O vs CPU | **CPU-bound puro** (cero I/O — todo en memoria) |

## Test soak

- `test_soak_million_operations` hace 1M operaciones aleatorias: add/rollback/tombstone/read
- **En cada operación "read" llama `h.timeline()`** (línea 405 del test)
- El test genera ~25k "read" con historial creciendo hasta ~50k+ versiones

## Top funciones por tiempo (cProfile, 100k ops)

| Función | Tottime | % | Observación |
|---|---|---|---|
| `timeline()` — fact_history.py:88 | 55.8s cum | 97.7% | `sorted(_versions.values())` |
| `<lambda>` key de sorted — :89 | 26.1s | 45.7% | 312M llamadas |
| `sorted` builtin | 29.7s | 52.1% | O(n log n) por llamada |
| add_version | 0.12s | 0.2% | Sano (O(1)) |
| rollback | 0.13s | 0.2% | Sano |
| random.choice | 0.14s | 0.2% | Sano |

## Análisis línea por línea

`timeline()` aislado (medición directa, 50 mediciones):

| Versiones en historial | timeline() por llamada |
|---|---|
| 1,000 | 0.05 ms |
| 5,000 | 0.28 ms |
| 10,000 | 0.51 ms |
| 25,000 | 1.42 ms |
| 50,000 | 2.92 ms |

- `add_version` aislado: 50k adds en **0.19s** (perfecto, O(1) con dict)
- Crecimiento de timeline(): O(n log n) por llamada — normal para un sort

## I/O vs CPU

- **Disco: 0%** — el test no toca disco (todo en memoria: dict + dataclasses)
- **CPU: 100%** del tiempo en `sorted()` + lambda key
- Conclusión: **CPU-bound**, sin componente de I/O

## Conclusión del diagnóstico

**El cuello de botella está en el TEST, NO en el motor.**

1. `timeline()` es O(n log n) — **2.7ms con 50k versiones es un coste razonable** para un método de consulta
2. `add_version`, `rollback`, `tombstone`, `version_count`, `current` — todos sanos (O(1))
3. El problema real: el test llama `timeline()` **en cada operación "read"** (24,815 veces en 100k ops), sobre un historial que crece sin límite → coste acumulado O(n² log n) → inviable a 1M

Esto es **Escenario B del plan** (problema en el test mismo — "test usa batch o reduce"), NO Escenario D (motor/).

## Recomendación

**Fix seguro (Fase 2, fuera de motor/):** en el test, reemplazar la llamada `_ = h.timeline()` del bloque "read" por una consulta O(1) (`h.current`, `h.version_count` ya se llaman) o amortizar timeline() (una vez cada 10k ops). El motor NO necesita cambios.

- Archivo afectado: `tests/infra/test_f25_b7_hardening.py:405` (el TEST)
- ¿Está en motor/core/knowledge? **NO** — es un archivo de tests
- Riesgo: bajo (no cambia API ni comportamiento del motor)

## Hallazgos adicionales

1. El test usa `@pytest.mark.timeout(600)` — insuficiente para la carga real (necesitaría >570s con la corrección del loop, o el loop corregido completa en segundos)
2. `timeline()` tiene 312M llamadas de lambda key en 100k ops — la lambda `lambda v: v.created_at` es evitable (key=attrgetter), pero NO es el problema (el sort en sí es necesario)
3. Los tests hermanos `test_benchmark_add_100k` (línea 306) y `test_benchmark_rollback_100k` (319) usan la misma API pero sin timeline() en el loop — confirman que el motor es sano

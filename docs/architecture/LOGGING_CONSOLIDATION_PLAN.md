# Plan de Consolidación de Logging

**Objetivo:** Unificar los 31 `logging.basicConfig` y 3 wrappers paralelos en una única implementación canónica sin cambiar el comportamiento observable.

**Estado:** ✅ COMPLETADO (v3.7.0-fase9)

## Estado Actual

### Núcleo real
- `motor/observability/logging.py` — `setup_logging()`, `JSONFormatter`, `ContextFilter`
- `motor/platform/logging.py` — alias `configure_logging = setup_logging`, `ComponentLogger`
- `core/json_logger.py` — `StructuredLogger` (wrapper propio con JSONFormatter)
- `knowledge/engine/logging_config.py` — `setup_logging()` condicional por env var

### 31 basicConfig dispersos

| Categoría | Cantidad | Ejemplos |
|-----------|----------|----------|
| Library (import-time) | 2 | `router.py:11`, `heartbeat.py:25` |
| `if __name__ == '__main__'` | 4 | `debate_engine.py`, `plan_validator.py`, `cleanup.py`, `watchdog_funciones.py` |
| App entry points | 2 | `app/motor_flujo.py`, `app/main.py` |
| Servicios systemd | 2 | `mantenimiento/*.py` |
| Standalone scripts | 4 | `agent_hierarchy.py`, `agente_sandbox_codigo.py`, `qdrant_retention.py`, `error_sandbox.py` |
| Scripts/pro benchmarks | 17 | `benchmark_*.py`, `chaos_test.py`, `metrics_server.py`, `index_*.py` |

### 83 loggers registrados (patrón `ura.<componente>`)

## Estrategia

### Fase A: Canonical setup_logging ✅
Enriquecer `motor/observability/logging.py:setup_logging()` para que acepte los mismos parámetros que `basicConfig`:
- `level`, `fmt`, `handlers`, `force` — exactamente la misma semántica
- Mantener defaults actuales (JSON Output) para no romper consumidores existentes

### Fase B: Migrar library modules ✅
Reemplazar `basicConfig` en módulos de librería que se ejecutan en import-time:
1. `core/model_router/router.py:11` → Eliminado (librería no configura logging)
2. `core/infra/heartbeat.py:25` → Movido a `main()` + `setup_logging()`

### Fase C: Migrar CLI entry point ✅
`motor/cli/main.py:_setup_logging()` delegado en `motor.observability.logging.setup_logging()`.

### Fase D: Migrar app entry points ✅
`app/motor_flujo.py`, `app/main.py` → basicConfig movido de module-level a `if __name__ == '__main__'`.

### Fase E: Migrar scripts sueltos ✅
`core/debate/debate_engine.py` → reemplazado por `setup_logging()`.
El resto ya estaban dentro de `if __name__` blocks (correcto).

### Fase F: Wrappers redundantes ⏳ PENDIENTE
- `core/json_logger.py` — mantiene compatibilidad
- `knowledge/engine/logging_config.py` — mantiene compatibilidad
- `motor/platform/logging.py` — ya es alias, ok

### Fase G: basicConfig residual 🟢 No crítico
17 scripts/pro benchmarks + 2 mantenimiento + agent_hierarchy.py mantienen basicConfig propio (son standalone scripts, patrón aceptable).

## Criterios de No Regresión
- Mismos formatos de salida (timestamp, level, message)
- Mismos niveles por módulo
- Mismos handlers (StreamHandler, FileHandler)
- Misma salida (stdout, stderr, archivo)
- pytest: 0 regresiones
- ruff: 0 errores nuevos
- bandit: sin issues nuevos
- mypy: sin regresiones (pre-existentes aceptadas)

## No Hacer
- No cambiar el comportamiento de `JSONFormatter`
- No unificar `core/json_logger.py` y `motor/platform/logging.py` aún (compatibilidad)
- No tocar los 17 scripts/pro benchmarks (bajo impacto, muchos formatos distintos)

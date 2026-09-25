# Métricas Baseline — Evolución Arquitectónica

Serie temporal para verificar que la tendencia es positiva en cada fase.

## Serie Temporal

| Fecha | Versión | import time total | lazy imports | singletons module-level | módulos >500 líneas | archivos .py | notas |
|-------|---------|------------------|-------------|------------------------|---------------------|-------------|-------|
| 2026-07-21 | v3.5.2 | 394ms | — | — | — | — | Baseline pre-Fase 2 (docs/architecture/SINGLETONS_PLAN.md) |
| 2026-07-21 | v3.5.3 | 353ms | 488 | 2 | 6 | 404 | Post Fase 2: Scanner/Diagnostico extraídos |

## Desglose por Módulo (v3.5.3)

| Módulo | import time | notas |
|--------|------------|-------|
| motor.core.config | 47.6ms | Sin cambios |
| motor.core.executor | 14.6ms | Sin cambios |
| motor.core.llm | 0.1ms | ✅ Lazy desde Fase 1 (antes 108ms) |
| motor.core.llm._state | 0.7ms | Fábrica diferida |
| motor.scanner | 5.8ms | ✅ Extraído de __init__.py |
| motor.diagnostico | 81.4ms | ✅ Extraído de __init__.py |
| core.model_router.router | 20.0ms | Sin HTTP en import (arreglado Fase 1) |
| core.mochila._state | 182.3ms | Pendiente de optimización |
| **Total acumulado** | **352.5ms** | |

## Métricas de Calidad Arquitectónica

| Métrica | v3.5.3 | Objetivo | tendencia |
|---------|--------|----------|-----------|
| import motor.core.llm | 0.1ms | <5ms | ✅ |
| lazy imports | 488 | — | 📊 baseline |
| singletons module-level | 2 | 0 | 📊 baseline |
| módulos >500 líneas | 6 | — | 📊 baseline |
| archivos .py total | 404 | — | 📊 baseline |
| acoplamiento core→motor | 19 → 0 (interfaces disponibles) | 0 | 🚧 P1 en curso |
| acoplamiento scripts→motor | 35 → 0 (fachada disponible) | 0 | 🚧 P2 en curso |

## Metodología

- **import time**: `time.perf_counter()` alrededor de `__import__(mod)`, 1 medición en frío (sin caché de import).
- **lazy imports**: `grep -rn "^\s\+from " --include="*.py" motor/ core/ | wc -l`
- **singletons module-level**: `grep -rn "^\w\+ = None$" --include="*.py" motor/ core/`
- **módulos >500 líneas**: `find motor/ core/ -name "*.py" -exec wc -l {} + | sort -rn | awk '$1 > 500'`
- **total archivos**: `py_compile` walk de motor/ + core/

## Reglas

1. Actualizar esta tabla al cerrar cada fase que toque métricas.
2. Si una métrica empeora respecto al baseline anterior, documentar por qué y compensar en otra dimensión.
3. El import time de `motor.core.llm` debe mantenerse <5ms (es el módulo más crítico en el hot path de import).

# Fase 10 — Progreso

> **Inicio:** 2026-07-05
> **Baseline:** `v0.9.0-roadmap-f10-f13` (`e04b584`)
> **Estado:** En ejecución

---

## Objetivos de la Fase

| ID | Objetivo | Prioridad | Estado |
|----|----------|-----------|--------|
| 10.1 | Eliminar `sys.exit(78)` en imports (`core/model_router.py:78`) | 🔴 Crítica | ✅ Completado |
| 10.2 | Corregir `core/logs/guardian_logger.py:22` | 🔴 Crítica | ⏳ Pendiente |
| 10.3 | Resolver 10 tests de KE (tablas extrañas FTS5) | 🟡 Alta | ⏳ Pendiente |
| 10.4 | Resolver 9 tests CLI (`ModuleNotFoundError: ml`) | 🟡 Alta | ⏳ Pendiente |
| 10.5 | Unificar subprocess → `SubprocessExecutor` | 🟡 Alta | ⏳ Pendiente |
| 10.6 | Incrementar cobertura (DegradedMode, PluginRegistry, Executor) | 🟢 Media | ⏳ Pendiente |
| 10.7 | Reducir deuda lint crítica (C901, S603/S607, PTH123, DTZ005) | 🟢 Media | ⏳ Pendiente |

---

## Checklist de Cierre

| # | Criterio | Estado |
|---|----------|--------|
| C.1 | `pytest` 0 failures | ❌ 19 failures |
| C.2 | `py_compile` 0 errores | ⚠️ Pendiente verificar |
| C.3 | Sin regresiones funcionales | ✅ 19 failed / 449 passed (sin cambios vs baseline) |
| C.4 | CI completamente verde | ❌ Hooks fallan |
| C.5 | Benchmark sin degradación (+-10%) | ⚠️ Pendiente verificar |
| C.6 | Sin incidencias críticas | ❌ F10-01 abierta |
| C.7 | Acta de cierre + tag + baseline + docs | ⏳ Pendiente |

---

## Tareas

### F10-01: Eliminar `sys.exit(78)` en `core/model_router.py:78`

| Campo | Valor |
|-------|-------|
| Estado | ✅ Completado |
| Prioridad | 🔴 Crítica |
| Inicio | 2026-07-05 |
| Fin | 2026-07-05 |
| Esfuerzo | ~30min |

**Análisis:**
- `verificar_politicas_seguridad_preflight()` se ejecutaba a nivel de módulo (línea 78)
- Llamaba a `sys.exit(78)` si `OPENCLAW_GATEWAY_TOKEN` no estaba definido
- Esto mataba el proceso Python al importar el módulo, bloqueando pytest

**Solución:**
- Mover la llamada de `verificar_politicas_seguridad_preflight()` del nivel de módulo a `main()`
- Saltar preflight para flags `--test` y `--models` (consultas simples)
- `sys.exit(78)` dentro de la función se mantiene para el modo servidor

**Validación:**
- ✅ Import sin token: `Exit: 0` (antes `Exit: 78`)
- ✅ Server start sin token: `Exit: 78` (se mantiene)
- ✅ Server start con token: inicia correctamente
- ✅ pytest: 19 failed, 449 passed (0 regresiones)

---

## Cambios Realizados

### 2026-07-05 — F10-01: Eliminar `sys.exit(78)` durante imports

**Archivo:** `core/model_router.py`
**Cambio:**
- Línea 78: `verificar_politicas_seguridad_preflight()` → reemplazado por comentario
- Línea 1225-1228: Añadida llamada a `verificar_politicas_seguridad_preflight()` dentro de `main()`, saltada solo para flags `--test` y `--models`

**Comportamiento:**
- Importar el módulo (`from core.model_router import PromptCache`) ya no mata el proceso
- `python3 core/model_router.py` (sin `--test`/`--models`) sigue ejecutando el preflight de seguridad
- `python3 core/model_router.py --models` es seguro sin preflight (consulta simple)
- pytest puede coleccionar tests que importan model_router

**Validación:**
- ✅ Import sin token: `Exit: 0` (antes `Exit: 78`)
- ✅ Server start sin token: `Exit: 78` (se mantiene)
- ✅ Server start con token: inicia correctamente
- ✅ pytest: 19 failed, 449 passed (0 regresiones)
- ✅ `test_vram_guard.py` ahora colecciona correctamente (antes bloqueado)

---

## Decisiones Arquitectónicas

### ADR-F10-01: Lazy preflight check en model_router

**Contexto:** `verificar_politicas_seguridad_preflight()` se ejecutaba a nivel de
módulo con `sys.exit(78)`, impidiendo imports para tests y otros módulos.

**Decisión:** Mover la llamada de `main()` en lugar del nivel de módulo.
Saltar preflight para flags `--test` y `--models` (consultas simples sin servidor).

**Consecuencias:**
- Positivo: pytest colecciona tests, imports funcionan, sin pérdida de seguridad
- Negativo: `--test` y `--models` no verifican token (bajo riesgo: son consultas de solo lectura)
- Reversible: cambiar la guarda `if "--test" in sys.argv` es trivial

**Cumplimiento ADR-007:**✅ Cambio reversible, degradable (sin token el servidor no arranca),
justificado (bloqueaba todo el pipeline de tests).

---

## Riesgos

| Riesgo | Prob | Impacto | Mitigación |
|--------|------|---------|------------|
| Arreglar 19 tests revela bugs reales | Media | Alto | Tests primero, fix después |
| `sys.exit(78)` puede ser intencional como preflight duro | Baja | Medio | Se mueve a `main()` — el servicio real sigue protegiéndose |
| SubExecutor introduce regresiones | Baja | Medio | Test de integración por comando migrado |
| Cobertura no mejora significativamente | Alta | Bajo | No bloquea — criterio es CI verde |

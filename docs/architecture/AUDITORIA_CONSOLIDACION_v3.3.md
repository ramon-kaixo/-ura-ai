# Auditoría de Consolidación v3.3

**Fecha:** 2026-07-20  
**Propósito:** Verificar robustez, acoplamiento y riesgos antes de avanzar a nuevo bloque funcional.

---

## 1. Acoplamientos entre componentes de autonomía

| Componente | Dependencias | Riesgo |
|-----------|-------------|--------|
| `goal_manager.py` | Solo `PipelineEngine` | 🟢 Bajo — no conoce Planner/Executor/Evaluator |
| `planner.py` | `PipelineEngine`, `plugin_registry.run_phase()` | 🟢 Bajo — depende de API estable |
| `evaluator.py` | `PipelineEngine` | 🟢 Bajo — solo usa `promotion.record()` y `check_budget()` |
| `learning.py` | `PipelineEngine` | 🟢 Bajo |
| `autonomy.py` | GoalManager, Planner, Evaluator, Learning, PipelineEngine | 🟡 Medio — orquestador, acoplamiento esperado |
| `learning/aprendizaje.py` | Solo `PipelineEngine` | 🟢 Bajo — imports diferidos dentro de funciones |

**Conclusión:** No hay acoplamientos ocultos. GoalManager no conoce Planner ni Evaluator. ADR-030 respetado.

---

## 2. Código duplicado

| Duplicación | Archivos | Líneas | Riesgo |
|------------|----------|--------|--------|
| Carga de ledger JSON | `learning.py:25-33` y `pattern_analyzer.py:24-32` | 9 líneas c/u | 🟡 Medio — lógica idéntica. Si se cambia una, la otra queda inconsistente. |
| Cierre de ledger | `autonomy.py:164-166` y `aprendizaje.py:104-107` | 3 líneas c/u | 🟢 Bajo — patrón de cierre estándar |

**Total duplicado:** ~24 líneas en 4 archivos.

---

## 3. APIs demasiado específicas

| API | Problema |
|-----|----------|
| `GoalManager.create(title, priority, budget, ...)` | Parámetros muy específicos de autonomía. Si otro componente quiere crear objetivos, debe acoplarse a esta API. |
| `Planner.GOAL_PHASE_MAP` | Hardcodea tipos de objetivo (`auditar`, `refactor`, `optimizar`, `documentar`, `test`). Nuevos tipos requieren modificar el Planner. |
| `PolicyEngine._allowed_policies` | Hardcodea políticas permitidas en modo autónomo. No es extensible sin modificar código. |

**Riesgo:** 🟡 Medio. Las APIs funcionan para el caso actual pero no son extensibles sin modificar el código.

---

## 4. Concurrencia con múltiples objetivos

| Componente | Thread-safe? | Evidencia |
|-----------|-------------|-----------|
| `GoalManager` | ❌ No | 0 locks, 0 threading imports. `_goals` dict compartido sin protección. |
| `Planner` | 🟢 Sí (secuencial) | Ejecuta `for phase in phases` — no hay paralelismo |
| `ExecutionLedger` | ❌ No | Sin locks. `_entry` dict modificado sin protección. |
| `PolicyEngine` | ❌ No | `_applied` lista sin protección |

**Riesgo:** 🟡 Medio. Con un solo orquestador secuencial no hay race conditions hoy. Si en el futuro se paralelizan objetivos, habrá que añadir locks.

---

## 5. Crecimiento del ExecutionLedger

| Métrica | Valor |
|---------|-------|
| Tamaño actual | ~100KB (11 archivos) |
| Archivos por ejecución | 1 archivo JSON |
| Crecimiento estimado | ~3.5KB por ejecución |
| Proyección anual | ~36,500 archivos, ~128MB |
| Política de retención | ❌ No existe — sin archive, sin rotación, sin purge |

**Riesgo:** 🟡 Medio a largo plazo. No urgente hoy (100KB), pero sin límite crecerá indefinidamente. Añadir `max_ledger_entries` o rotación por fecha.

**Evidencia:** `ledger.py:133` — `save()` escribe sin comprobar tamaño.

---

## 6. Aprendizaje que puede degradar el comportamiento

| Riesgo | Descripción | Severidad |
|--------|-------------|-----------|
| Timeout sin límite superior | `recommended_timeouts()` usa media+2σ sin capping. Un plugin que se cuelgue una vez puede generar timeouts de horas. | 🔴 Medio |
| Sin verificación de causalidad | PatternAnalyzer correlaciona, no causa. `plugin_fail_X: 3` no implica que X sea el problema real. | 🟡 Medio |
| PolicyEngine sin rate limit | En modo autónomo puede aplicar N políticas por ejecución sin control. | 🟡 Bajo |

**Evidencia:**
- `learning.py:53` — `recommended = int(avg + 2 * stdev) + 5` sin `max()` superior
- `policy_engine.py:71` — `_apply_policy()` sin límite de llamadas por ciclo

---

## 7. Riesgos para ADR-030

| Requisito ADR-030 | Estado |
|-------------------|--------|
| No modificar PipelineEngine APIs existentes | ✅ Cumplido |
| ExecutionLedger extensiones = campos opcionales | ✅ Cumplido (pattern_detections, knowledge, etc. son arrays vacíos por defecto) |
| plugin_registry solo campos opcionales | ✅ Cumplido (capability default "infrastructure") |
| tuneladoras sin cambios | ✅ Cumplido |
| checkpoints sin cambios | ✅ Cumplido |

**Riesgo:** 🟢 Bajo. ADR-030 se ha respetado en todas las extensiones.

---

## Resumen de hallazgos

| # | Hallazgo | Severidad | Archivos |
|---|----------|-----------|----------|
| D1 | Carga de ledger duplicada (9 líneas idénticas) | 🟡 Media | `learning.py`, `pattern_analyzer.py` |
| D2 | APIs específicas (GOAL_PHASE_MAP, _allowed_policies) | 🟡 Media | `planner.py`, `policy_engine.py` |
| D3 | Sin concurrencia (0 locks en GoalManager) | 🟡 Media | `goal_manager.py` |
| D4 | Ledger sin rotación | 🟡 Media | `ledger.py` |
| D5 | Timeout sin límite superior en learning | 🔴 Media | `learning.py` |
| D6 | Sin rate limit en PolicyEngine | 🟡 Baja | `policy_engine.py` |
| ADR-030 | 0 violaciones | 🟢 OK | — |

---

## Veredicto

**Puntuación:** 7/10. La base es sólida, ADR-030 se ha respetado, no hay dependencias circulares ni acoplamientos ocultos. Los hallazgos son mejoras, no bloqueantes.

**Lo más crítico:** D5 — timeout sin límite superior puede causar timeouts excesivos, degradando la siguiente ejecución. Corregir antes de pasar a modo autónomo completo.

**Lo más urgente a medio plazo:** D4 — rotación del Ledger antes de que alcance tamaños problemáticos.

**¿Preparado para siguiente bloque funcional?** Sí, con la advertencia de corregir D5 (límite superior en timeouts recomendados) antes de confiar en el aprendizaje autónomo.

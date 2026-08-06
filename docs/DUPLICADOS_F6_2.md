# DUPLICADOS F6.2 — Auditoría de módulos restaurados

**Fecha:** 2026-08-06
**Contexto:** F6.2 restauró módulos con consumidores vivos desde `.attic/tools/scripts_pro/purga-v4-cadenas/`
(commit `f25f68bd`). Este doc verifica si duplican funcionalidad existente.

## 1. scripts/pro/autonomy/ vs motor/agents/ y motor/intelligence/

| Módulo autonomy | ¿Duplica? | Evidencia |
|---|---|---|
| `autonomy/goal_manager.py` (GoalManager) | ❌ **NO** | `motor/intelligence/goals/` NO existe; `motor/intelligence/agents/` (7 ABCs) ni `motor/agents/` (6 módulos, CapabilityGate/ToolRunner/Scheduler) implementan gestión de objetivos/metas |
| `autonomy/learning/*` (8 módulos) | ❌ **NO** | `motor/intelligence/learning/` NO existe; `motor/intelligence/memory/` (base, episodic, semantic, hybrid, forgetting) es memoria no aprendizaje de patrones. `grep -rln "class GoalManager\|class PatternAnalyzer\|class KnowledgeBase\|class PolicyEngine" motor/` = 0 |
| `autonomy/swarm/agents/*` (7 agentes) | ❌ **NO** | Nada equivalente en `motor/`. Los swarm-agent importan `autonomy.*` interno (auto-consumo) |

**Conclusión 1:** autonomy es código único de scripts/pro, sin paralelo en motor/. **NO duplica.**

## 2. scripts/pro/reuse/ vs archivos sueltos

| Archivo | ¿Suelto duplicado? | Evidencia |
|---|---|---|
| `reuse/reuse_detector.py` | ❌ | `scripts/pro/reuse_detector.py` NO EXISTE |
| `reuse/quality_gates.py` | ❌ | `scripts/pro/quality_gates.py` NO EXISTE |

**Conclusión 2:** NO hay duplicados sueltos; los submódulos solo existen dentro de `reuse/`.

## 3. scripts/pro/reglas_*.py

Ternio existente: `reglas_applier.py`, `reglas_generator.py` (restaurados) + `reglas_loader.py` (no restaurado, ya existía).

| Función | applier | generator | loader | Duplicado |
|---|---|---|---|---|
| `_extraer_nombre_f821` | ✅ | ✅ | — | ⚠️ **DUPLICADA** dentro de scripts/pro |
| `_es_import_estandar` | ✅ | ✅ | — | ⚠️ **DUPLICADA** dentro de scripts/pro |
| `aplicar_regla_a_codigo` | ✅ | — | — | único |
| `detectar_f821_en_codigo` | ✅ | — | — | único |
| `generar_reglas_desde_patrones` | — | ✅ | — | único |
| `actualizar_reglas` | — | ✅ | — | único |
| `cargar_reglas/guardar_reglas` | — | — | ✅ | único |

**Consumidores:** `scripts/pro/auto_reglas.py` (úNico con `Learnings/import`); sin importadores en `motor/`, `knowledge/`.

**Conclusión 3:** los ternos no duplican funcionalidad de motor/. **Deuda menor interna**: `_extraer_nombre_f821` + `_es_import_estandar` duplicadas entre applier y generator (origen de la restauración, no regresión nueva).

## 4. Mapa general

| Vía | Resultado |
|---|---|
| autonomy vs motor | 0 coincidencias (nueva funcionalidad) |
| reuse vs sueltos | 0 duplicados |
| reglas vs motor/knowledge | 0 coincidencias |

**Acción recomendada (siempre decisión Ramón):** archivar en sesión futura solo la deuda `_extraer_nombre_f821`/`_es_import_estandar` (dedup en generator re-exporta de applier). Nada se elimina en este bloque.
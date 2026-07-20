# AUDITORÍA DE CONSOLIDACIÓN v1.0

**Fecha:** 2026-07-20  
**Propósito:** Verificar consistencia post-migraciones antes de iniciar nuevas fases.

---

## 1. APIs antiguas — referencias residuales

| API antigua | Buscada en | Resultado |
|---|---|---|
| `core.mochila.providers` imports | Todo el código | ✅ **0 referencias** |
| `ProviderError` (fuera de providers/) | Todo el código | ✅ **0 referencias** |
| `core.json_logger` (import directo) | Todo el código | ✅ **0 referencias** |
| `motor.platform.logging` (import directo) | Todo el código | ✅ **0 referencias** |
| `knowledge.engine.logging_config` → patrón antiguo | knowledge/ | ✅ **Delega a motor** |

## 2. Código duplicado — estado post-consolidación

| Patrón | Antes | Ahora | Criterio |
|---|---|---|---|
| CircuitBreaker | 4 implementaciones | **2** (1 canónica + 1 mochila legacy) | ✅ Consolidado |
| Logging | 4 sistemas | **1** (motor/observability/logging.py) | ✅ Consolidado |
| LLM Providers (Gemini/Ollama/OpenRouter) | core/ + motor/ | **motor/ + adapter** | ✅ Migrado |
| EventBus | core/ + motor/ + knowledge/ | **3** (pendiente) | 🟡 No migrado |
| Memory layer | core/memoria/ + motor/memory/ | **2** (diferente propósito) | 🟡 Documentado |

## 3. Imports rotos

| Archivo | Línea | Import | Estado |
|---|---|---|---|
| `core/memoria/consulta.py` | 9 | `from core.memoria.ingesto import procesados_local` | 🔴 **ROTO** — `procesados_local` no existe en `ingesto.py`. Stub. Pre-existente. |

## 4. TODO/FIXME/HACK

**0 encontrados** en código de producción. ✅ Solo referencias en documentación y AST checks.

## 5. noqa / type: ignore

| Categoría | Count | Evaluación |
|---|---|---|
| `# noqa: PTH123` | 38 | Mayoría en rutas legacy, aceptable |
| `# noqa: S110` | 37 | Degradación controlada documentada |
| `# noqa: PLW0603` | 36 | Uso de global en scripts |
| `# noqa: F401` | 12 | Mayoría en re-exports intencionales (__init__.py) |
| `type: ignore` | 19 | Tests principalmente |
| `pragma: no cover` | 0 | ✅ Sin abuso |

## 6. Dependencias circulares

| Dirección | Archivos | Tipo |
|---|---|---|
| `motor/` → `core/` | 1 (`motor/cli/cmd_ura.py`) | 🟢 Legítimo (CLI llama a core) |
| `core/` → `motor/` | 18 archivos | 🟢 Legítimo (core usa motor como framework) |
| Ciclo cerrado | **0** | ✅ Sin dependencias circulares |

## 7. Tests

| Suite | Tests | Resultado |
|---|---|---|
| platform_resilience | 29 | ✅ Pass |
| platform_delivery | ~40 | ✅ Pass |
| core_secrets | ~15 | ✅ Pass |
| Additional suites | ~500 | ✅ Pass |
| **Cobertura global** | 17.26% | 🟡 Por debajo del threshold 20% |

## 8. Herramientas

| Herramienta | Resultado |
|---|---|
| Ruff (mochila_server.py) | ✅ 0 errors |
| Ruff (global, select=ALL) | 93 errors (62 EXE001 cosmético, 31 pre-existentes) |
| Mypy (motor/) | ✅ 0 errors |
| Bandit (motor/) | ✅ 0 Medium/High |
| Audit reproducible | ✅ PASS (compile + tests) |

## 9. Conclusiones

**Incidencias encontradas:**
1. 🔴 `core/memoria/consulta.py:9` — import roto (`procesados_local` no existe). Pre-existente, no causado por migraciones.
2. 🟡 Cobertura 17.26% por debajo de threshold 20%.

**No hay regresiones funcionales.** Todas las migraciones (CircuitBreaker, logging, providers, IPs) han sido verificadas y no introdujeron nuevos errores.

**El repositorio está estable para la siguiente fase.**

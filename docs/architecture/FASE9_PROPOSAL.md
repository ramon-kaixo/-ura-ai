# Propuesta — Fase 9: Impacto Funcional y Consolidación Arquitectónica

> **Versión:** 3.0 (revisada tras auditoría)
> **Fecha:** 2026-07-04
> **Estado:** ✅ Aprobada
> **Fase anterior:** Auditoría Arquitectónica Post-Fase 8 (`v0.7.1-audit-fase8`)

---

## Principio Rector

Solo trabajo con **impacto funcional o arquitectónico demostrable**.  
La deuda técnica residual (lint, FTS, tests dependientes del entorno,
archivos Unicode, limpieza menor) queda en backlog independiente y
no bloquea ni se mezcla con esta fase.

---

## Stream C — Modo Degradado Explícito y Observable (Funcional)

**Estado:** ✅ COMPLETADO (v3.0)

Ver `docs/architecture/DEGRADED_MODE.md` para especificación completa.

**Implementado:**
1. `motor/core/state.py` — Clase `DegradedMode` (singleton thread-safe con RLock)
2. Puntos de falla integrados:
   - `motor/core/qdrant_client.py` (conexión/health)
   - `knowledge/engine/qdrant_sync.py` (_get_qdrant)
   - `core/mochila/providers/ollama.py`, `gemini.py`, `groq.py`, `deepseek.py`, `openrouter.py` (health)
3. Endpoint `GET /api/v1/status` en `ejecutor_api.py` (200 si saludable, 503 si degradado)
4. Logging WARNING en cada transición normal↔degradado
5. Documentación en `docs/architecture/DEGRADED_MODE.md`

**Verificación:** 9 archivos compilan, 0 errores de lint nuevos, tests unitarios
de DegradedMode pasan (incluyendo concurrencia).

---

## Stream B — Modularidad y Abstracción de Ejecución (Arquitectura)

**Problema:** ~110+ llamadas `subprocess.run()` en ~45 archivos sin abstracción
unificada. Cada archivo implementa su propio patrón de timeouts, logging, y
manejo de errores. `plugin_registry.py` descubre plugins por parseo AST (variable
`PLUGIN = {...}`) y los ejecuta como subprocesos separados. 1 instancia de
`shell=True` residual en `monitor/snc.py`.

**Análisis:**
- `motor/core/executor.py` no existe — no hay un `BaseExecutor` o `ProcessResult`
- `plugin_registry.py` usa `subprocess.run([sys.executable, script, ...])` en vez
  de `importlib` dinámico
- `cli/__init__.py` (raíz) importa `cli.gatekeeper` que no existe — dead code
- `ejecutor_api.py:210` usa `time.time()` sin `import time`

**Acción:**

| Sub-paso | Descripción | Archivos |
|----------|-------------|----------|
| B.1 | Crear `motor/core/executor.py`: `BaseExecutor`, `SubprocessExecutor`, `ProcessResult` con timeout/retry/logging unificado | 1 nuevo |
| B.2 | Crear `motor/plugin/` con `PluginBase`, registry vía `importlib` (reemplazar AST+subprocess) | 3-4 nuevos |
| B.3 | Eliminar `shell=True` en `monitor/snc.py:117` | 1 modificado |
| B.4 | Eliminar `cli/__init__.py` (raíz) — dead code | 1 eliminado |
| B.5 | Fix `import time` en `ejecutor_api.py:210` (bug pre-existente) | 1 modificado |
| B.6 | Migrar `curl` → `httpx` en `ura_multi_agent.py` y `monitor/openclaw.py` | 2 modificados |

**Impacto:** Un único punto para timeouts, retries, logging, degradación,
auditoría y seguridad. Eliminación de código duplicado. Pipeline extensible
vía importlib sin overhead de subprocess.

---

## Stream D — Refactor de `ura.py` (Arquitectura)

**Problema:** `ura.py` (583 líneas) expone 16 comandos con `sys.argv` manual
(if/elif en `main()`), sin argparse, sin console_scripts, sin tests.
Usa SSH para 4 comandos (index, ask, maintenance, snc). Depende de
`tests/test_unit.py` en 3 lugares (líneas 53, 327, 380).

**Análisis:**
- `motor/cli/main.py` ya existe con argparse y 21 subcomandos
- `ura.py` y `motor.cli.main` tienen comandos completamente diferentes —
  "delegar en motor.cli.main" no funciona sin portar 16 comandos
- `motor/cli/` ya tiene `cmd_diag.py`, `cmd_pipeline.py`, `cmd_status.py`, `cmd_utils.py`
- **ura.py NO se elimina** durante esta fase — se mantiene como wrapper

**Acción:**

| Sub-paso | Descripción | Archivos |
|----------|-------------|----------|
| D.1 | Extraer funciones comando a `motor/cli/cmd_ura.py` (módulo único) | 1 nuevo |
| D.2 | Registrar en `motor/cli/main.py` argparse + COMMANDS + URA_COMMANDS | 1 modificado |
| D.3 | Reducir `ura.py` a wrapper (~52 líneas) que delega en `motor.cli.main` | 1 modificado |
| D.4 | Añadir console_scripts: `ura = ura:main` en pyproject.toml | 1 modificado |

**Regla:** `ura.py` se mantiene como wrapper durante toda la Fase 9. Solo
se elimina tras validación en Fase E + varias iteraciones de compatibilidad.

**Impacto:** `ura.py` de 583→52 líneas. 17 comandos portados a `motor/cli/cmd_ura.py`.
`ura <comando>` desde PATH (console_scripts). Arquitectura mantenible.

---

## Stream A — Consolidación de Test Runners (Calidad)

**Problema:** `tests/test_unit.py` (481) y `tests/unit_test_runner.py` (490)
son ~95% duplicados. 4 tests en `motor/tests/` no descubiertos por pytest.
5 tests huérfanos en raíz del proyecto. 5 scripts shell referencian tests
que no existen.

**Nota:** Este Stream va al **final** porque `ura.py` depende de
`test_unit.py`. Si se modifica antes de refactorizar ura.py (Stream D),
se rompe esa dependencia.

**Acción:**

| Sub-paso | Descripción | Archivos |
|----------|-------------|----------|
| A.1 | Fusionar `test_unit.py` + `unit_test_runner.py` (superset, merge diferencias) | 2→1 |
| A.2 | Fusionar `test_memory_engine.py` + `test_properties.py` → `test_hypothesis.py` | 2→1 |
| A.3 | Mover 5 tests huérfanos de raíz a `tests/` | 5 movidos |
| A.4 | Añadir `"motor/tests"` a `testpaths` en pyproject.toml | 1 modificado |
| A.5 | Unificar `make test` → `make pytest` en Makefile | 1 modificado |
| A.6 | Eliminar referencias a tests inexistentes en `scripts/pro/phase1_diagnosis.sh` | 1 modificado |
| A.7 | Limpiar `motor/tests/conftest.py` (vacío → eliminado) | 1 eliminado |

**Cobertura:** NO se fuerza un umbral mínimo (ej. 30%) durante esta fase.
Primero se aumenta cobertura real, luego se endurece el límite.

---

## Stream E — Validación Final (Cierre)

**Problema:** Sin una fase de validación explícita, el cierre de Fase 9
no es verificable objetivamente.

**Acción:**

| # | Check | Criterio |
|---|-------|----------|
| E.1 | Compilación completa | `py_compile` 0 errores en todos los módulos tocados |
| E.2 | Ruff sin errores nuevos | `ruff check` — 0 errores nuevos vs baseline |
| E.3 | Pytest con nuevo recuento | `pytest -q` — mismo resultado que baseline (sin regresiones) |
| E.4 | Smoke tests CLI | `ura.py help/status/doctor/finalize --help` funcionan |
| E.5 | Smoke tests API | `ejecutor_api` endpoints /health, /api/v1/status responden |
| E.6 | Descubrimiento de plugins | `PluginRegistry.discover()` encuentra plugins sin errores |
| E.7 | Verificación de DegradedMode | `DegradedMode` inicializa, degrada, restaura correctamente |
| E.8 | Comparación con baseline | diff de tests vs baseline commit (`0d5aed7`) |
| E.9 | Working tree limpio | `git status` sin cambios sin commitear |
| E.10 | Documentación sincronizada | AGENTS.md + FASE9_PROPOSAL.md reflejan estado real |

**Impacto:** Cierre verificable. Baseline actualizado. Trazabilidad completa.

---

## Orden de Ejecución Definitivo (Revisado v3.0)

```
C ──► B ──► D ──► A ──► E
```

### Justificación del cambio respecto a v2.0

El orden anterior era `C → A → B → D`. La auditoría descubrió que
`ura.py` (Stream D) depende de `tests/test_unit.py` (Stream A) en 3 lugares.
Si A se ejecuta antes que D, `ura.py` se rompe.

El nuevo orden `C → B → D → A → E`:
1. **C** — completado (DegradedMode, /api/v1/status)
2. **B** — completado (executor.py, plugin/, shell=True eliminado)
3. **D** — completado (ura.py→wrapper, motor/cli/cmd_ura.py, console_scripts)
4. **A** — completado (tests fusionados, Makefile, tests huérfanos movidos)
5. **E** — validación final: checklist de 10 puntos

### Dependencias Reales

```
┌───┐
│ C │ ← ✅ COMPLETADO
└───┘
  │
┌─▼──┐
│ B  │ ← ✅ COMPLETADO
└─┬──┘
  │
┌─▼──┐
│ D  │ ← ✅ COMPLETADO
└─┬──┘
  │
┌─▼──┐
│ A  │ ← ✅ COMPLETADO
└─┬──┘
  │
┌─▼──┐
│ E  │ ← EJECUTÁNDOSE
└───┘
└─┬──┘
  │ D → A: D elimina dependencia de test_unit.py, liberando A
┌─▼──┐
│ A  │ ← captura tests de B y D
└─┬──┘
  │
┌─▼──┐
│ E  │ ← validación final sin dependencias funcionales
└────┘
```

---

## Regla de Validación Obligatoria (Fase 9)

**Ningún stream se da por finalizado hasta superar su validación completa:**

```
┌─────────────────────────────────────────────┐
│ 1. Tests: pytest -q sobre el código afectado │
│ 2. Lint: ruff check sobre archivos tocados  │
│ 3. Docs: AGENTS.md actualizado si aplica     │
│ 4. Regresiones: 0 tests rotos pre-existentes │
│ 5. Commit + push a origin                    │
└─────────────────────────────────────────────┘
```

Cada stream produce un commit independiente y verificable. No se avanza
al siguiente stream hasta que el anterior está validado y pusheado.

---

## Criterios de Aceptación

| Stream | Criterio | Verificación |
|--------|----------|-------------|
| C | `GET /api/v1/status` retorna JSON con degraded/healthy | `curl localhost:4096/api/v1/status` |
| B | `SubprocessExecutor.run()` unifica timeouts/logging | Test unitario + lint |
| B | `plugin_registry` carga plugins via importlib | Import + ejecución en proceso |
| B | 0 instancias de `shell=True` | `grep -r 'shell=True' --include='*.py'` |
| D | Todos los comandos de `ura.py <cmd>` funcionan igual | Script de regresión comparativo |
| D | `ura <cmd>` desde PATH funciona | `pip install -e . && ura status` |
| A | `pytest tests/ -q` + `pytest motor/tests/ -q` sin exclusiones | `make pytest` exitoso |
| E | Benchmark no muestra regresión >5% | Comparación baseline |

---

## Backlog de Deuda Técnica (No Bloqueante, No Incluido en Fase 9)

| ID | Ítem | Prioridad | Notas |
|----|------|-----------|-------|
| T01 | `core/synonyms.json` chattr +i | Mínima | `sudo chattr -i && rm` |
| T02 | `sanear_codigo.py:50` syntax error | Baja | String no cerrado |
| T03 | 12 archivos .py con caracteres no-ASCII | Baja | Renombrar |
| T04 | 5 tests CLI fallan (deps entorno) | Baja | `@pytest.mark.skipif` |
| T05 | FTS schema verifier falso positivo | Media | Ignorar tablas FTS |
| T06 | ~2.356 lint errors (ruff all rules) | Baja | Refactor progresivo |
| T07 | `adapters/` nunca creado | Informativa | Decidir crear o remover |
| T08 | ~80+ `except: pass` sin auditar | Media | Auditoría postergada |

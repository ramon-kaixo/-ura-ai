# PIPELINE — Arquitectura Canónica v4.0

**Fecha:** 2026-08-06
**Fase:** 4 del Plan v4.0 (`docs/ARQUITECTURA_v4.0_PLAN.md`)
**Estado:** Documentación de referencia — VERIFICADO contra código y producción

---

## 1. Pipeline Canónico (motor de mejora continua)

El núcleo del pipeline vive en `scripts/pro/tuneladora/` (siempre importado como
`scripts.pro.tuneladora.*`, nunca relativo):

| Módulo | Rol |
|---|---|
| `engine.py` | `PipelineEngine` — motor de fases |
| `config.py` | `Configuration` — config unificada |
| `logger.py` | `Logger` — logging |
| `checkpoint.py` | `Checkpoint` — estado/punto de control |
| `ledger.py` | Ledger de fases |
| `snapshot.py` | `SnapshotService` — snapshots en `.nervioso/` |
| `detector.py` | Detector de oportunidades |
| `auto_trigger.py` | Disparo automático |
| `preflight_system.py` | Preflight del sistema |
| `resilience.py`, `notifier.py`, `scheduler.py`, `unified_scheduler.py`, `scheduler_daemon.py` | Orquestación |
| `watch_daemon.sh` | Daemon de watch (activación cron) |
| `pipeline/` | Sub-pipeline: `runner`, `sandbox`, `block_reviewer`, `sofia`, `tools/`, `pending_queue`, `snapshot_manager`, `llm_fallback` |
| `memory/` | Memoria de tuneladora: `short_term`, `long_term`, `episodic`, `semantic` |
| `plugins/` | Plugins de fase (`arq_check`, etc.) |

**Puntos de entrada oficiales** (los únicos invocadores externos con vida):

| Entrada | Uso |
|---|---|
| `scripts/pro/tuneladora_mejora.py` | Pipeline de Mejora Continua (fases `pre`, `refactor_plugins`, `pipeline_refactor`, `post`). Invoca `pipeline_refactor.py` como fase |
| `scripts/pro/tuneladora_mantenimiento.py` | Pipeline de Mantenimiento (6 fases). Timer systemd |
| `scripts/pro/pipeline_refactor.py` | Pipeline de Refactorización independiente (docstring: "invocable desde mejora continua") |
| `scripts/pro/pipeline_supremo.py` | Pipeline invocado desde `core/ingestador_red.py:122` (comando `refactorizar`) |

### Cadena de invocación verificada

```
Makefile / timer systemd
  └─ tuneladora_mantenimiento.py      (537 líneas, canon)
  └─ tuneladora_mejora.py
       └─ engine.PipelineEngine
       └─ plugins.refactor_plugins / pipeline_refactor
            └─ pipeline_refactor.py  (usa tuneladora.config/logger/snapshot + worker_manager)

core/ingestador_red.py:122 (producción)
  └─ pipeline_supremo.py (subprocess)
       └─ conciencia.py .py ORCH (inline)  → 10 pasos por subprocess
```

---

## 2. Consumidores verificados

| Consumidor | Qué invoca | Tipo |
|---|---|---|
| `core/ingestador_red.py:122` | `pipeline_supremo.py {archivo}` | subprocess (producción) |
| `scripts/pro/consolidacion.py:73` | `pipeline_refactor.py --workers 2` | subprocess (service FAILED) |
| `scripts/pro/tuneladora_mejora.py:114` | `pipeline_refactor` (fase) | motor |
| `tests/unit/test_ingestador_red.py` | `pipeline_supremo` | test |

---

## 3. Estado de salud de las púas de script invocadas (v4.0)

**`scripts/pro/pipeline_supremo.py` — DEGRADADO.** Invoca por subprocess a 10 scripts de `scripts/pro/`, de los cuales **7 están archivados** en `.attic/tools/scripts_pro/`:

| Invocado | Estado | Ubicación |
|---|---|---|
| `conciencia.py` | ✅ VIVO | `scripts/pro/` (también en `core/agents/` y `build/lib/`) |
| `auto_reglas.py` | ✅ VIVO | `scripts/pro/` |
| `compactadora.py` | ✅ VIVO | `scripts/pro/` |
| `token_screen.py` | ❌ ARCHIVADO | `.attic/tools/scripts_pro/token_screen.py` |
| `scanner_autoajuste.py` | ❌ ARCHIVADO | `.attic/tools/scripts_pro/scanner_autoajuste.py` |
| `inspectores.py` | ❌ ARCHIVADO | `.attic/tools/scripts_pro/inspectores.py` |
| `poda_mecanica.py` | ❌ ARCHIVADO | `.attic/tools/scripts_pro/poda_mecanica.py` |
| `openclaw_reviewer.py` | ❌ ARCHIVADO | `.attic/tools/scripts_pro/openclaw_reviewer.py` |
| `alineador.py` | ❌ ARCHIVADO | `.attic/tools/scripts_pro/alineador.py` |
| `plan_validator.py` | ❌ NO EXISTE | en ningún lado (repo ni .attic) |

Cada paso en `pipeline_supremo.py` enmarca el `subprocess.run` y actualiza `conciencia.py` con estado `idle/activo/bloqueado`; si el script falta el paso reporta `"ok": False` pero no aborta el pipeline (degradación controlada). **Riesgo:** 7/10 pasos del pipeline de refactorización de red están inertes tras la purga 2026-08-05.

**`tuneladora_mantung.py` — DEGRADADO.** Referencias a archivados:

| Script invocado | Refs en tuneladora_mantenimiento |
|---|---|
| `token_screen` | 9 |
| `conciencia` | 9 |
| `inspectores` | 7 |
| `analizar_fallo_conciencia` | 3 |
| `compactadora` | 6 |
| `scanner_autoajuste` | 2 |
| `auto_reglas` | 2 |
| `poda_mecanica` | 1 |

**NOTA:** `tuneladora_mantenimiento.py` está protegida (regla de no-touch de Ramón). Los pasos que detectan que el script falta deben capturar y degradar con log, no abortar. **REVISAR en F6.2 (bloqueada → Ramón).**

**`pipeline_refactor.py` — SANO.** No referencia scripts archivados; usa solo el motor `tuneladora/` + `worker_manager`. Es el único de los 3 pipelines sin deuda de refs.

---

## 3. Inventario de dead-ends v4.0

| Ruta | Veredicto | Meta |
|---|---|---|
| `scripts/pro/tuneladora/pipeline/` | ✅ vivo (usado por tuneladora) | conservar |
| `scripts/pro/tuneladora_pipeline.py` | ❌ NO existe | — |
| `scripts/pro/pipeline_refactor.py` | ✅ VIVO canónico | conservar |
| `scripts/pro/pipeline_supremo.py` | 🟡 VIVO pero DEGRADADO (7 refs a archivados + 1 perdida) | F6.2 restaurar invocados o degradar |
| `scripts/pro/pipeline_supremo.py` | es invocado por producción | NO archivar |
| `deploy/timers/*.timer` | varios se quedan sin reload | F7 limpieza |

---

## 4. Conclusión F4

- ✅ Creado este documento (canónico = `tuneladora/` + invocadores determinados).
- 🟡 `pipeline_supremo.py` necesita F6.2 (reparar 7 refs → decisión Ramón: restaurar de `.attic` o dejar degradado).
- 🟡 `tuneladora_mantenimiento.py` necesita F6.2 (mismo dilema, protegido por regla no-touch).
- ℹ️ Los pasos de `pipeline_supremo.py` ya degradan en vez de abortar (patrón defensivo verificado en código).
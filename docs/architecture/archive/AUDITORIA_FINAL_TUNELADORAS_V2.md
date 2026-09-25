# AUDITORÍA FINAL — Migración a Tuneladoras v2

**Fecha:** 2026-07-20  
**Estado:** ✅ COMPLETADO — Arquitectura oficial

---

## Diagrama de arquitectura final

```
┌──────────────────────────────────────────────────────────────────┐
│                     SCHEDULER (systemd)                          │
│              ura-maintenance-v2.timer (cada 6h)                  │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│               TUNELADORA DE MANTENIMIENTO                        │
│         scripts/pro/tuneladora_mantenimiento.py                  │
│                                                                  │
│  Responsabilidad: health checks, limpieza, validaciones,         │
│  diagnósticos, monitorización. NUNCA modifica código.            │
│                                                                  │
│  ┌────────────┐  ┌──────────────┐  ┌────────────┐  ┌──────────┐ │
│  │  Health    │  │CodeQuality   │  │  Cleanup   │  │Reporting │ │
│  │  Plugin    │  │Plugin        │  │  Plugin    │  │Plugin    │ │
│  └────────────┘  └──────────────┘  └────────────┘  └──────────┘ │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│               TUNELADORA DE MEJORA CONTINUA                      │
│         scripts/pro/tuneladora_mejora.py                         │
│                                                                  │
│  Responsabilidad: plugins, mejoras, lanzar refactorización.      │
│  Usa plugin_registry (fases pre/refactor/post).                  │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  ── Decisión: ¿Hay trabajo de refactorización?              │ │
│  │                                                             │ │
│  │  plugins refactor ¿modificaron archivos?                    │ │
│  │       │                      │                              │ │
│  │      Sí                      No                             │ │
│  │       │                      │                              │ │
│  │       ▼                      ▼                              │ │
│  │  Pipeline Refactor      Informe y fin                       │ │
│  └─────────────────────────────────────────────────────────────┘ │
└────────────────────────┬─────────────────────────────────────────┘
                         │  (solo si hay cambios)
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│               PIPELINE DE REFACTORIZACIÓN                        │
│         scripts/pro/pipeline_refactor.py                         │
│                                                                  │
│  Responsabilidad: descubrir archivos, distribuir trabajo,        │
│  lanzar workers, validar cambios, devolver éxito/error.          │
│  SOLO invocable desde Mejora Continua.                           │
│  NO tiene timer propio. NO tiene entry point directo.            │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│                    WORKER MANAGER                                │
│         scripts/pro/worker_manager.py                            │
│                                                                  │
│  Gestiona N workers en paralelo vía ThreadPoolExecutor.          │
│  Handshake con sistema nervioso (sistema_map.json).              │
└───────────┬───────────────────────────┬──────────────────────────┘
            │                           │
            ▼                           ▼
┌──────────────────────┐   ┌──────────────────────────────┐
│   RefactorWorker 1   │   │   RefactorWorker 2..N        │
│  refactor_worker.py  │   │  refactor_large_functions_v2 │
└──────────────────────┘   └──────────────────────────────┘
            │                           │
            └───────────┬───────────────┘
                        ▼
┌──────────────────────────────────────────────────────────────────┐
│                     VALIDACIÓN                                   │
│  plugin_registry (fase post) + f821_watch + ruff                │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│                     SNAPSHOT                                     │
│     SnapshotService → openclaw_firmador.delta_snapshot           │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│                     REPORTING                                    │
│     Logger (archivo + stdout) + estado_mantenimiento.json        │
└──────────────────────────────────────────────────────────────────┘
```

---

## Motor compartido (PipelineEngine)

```
scripts/pro/tuneladora/
├── __init__.py      ← Package, exporta Configuration, Logger, SnapshotService, PipelineEngine
├── config.py        ← Configuration: URA_ROOT, Ollama, Qdrant, timeouts (env vars + defaults)
├── logger.py        ← Logger: archivo + stdout, informes formateados
├── snapshot.py      ← SnapshotService: adaptador a openclaw_firmador.delta_snapshot
├── engine.py        ← PipelineEngine: orquestador puro (run_script, run_ruff, run_git, health)
└── plugins/
    ├── __init__.py
    ├── health.py        ← HealthPlugin: RAM, disco, Ollama, zombies
    ├── code_quality.py  ← CodeQualityPlugin: ruff, scanner, poda, f821
    ├── cleanup.py       ← CleanupPlugin: forense, git, auditoria, watermark, conciencia
    └── reporting.py     ← ReportingPlugin: estado, informes
```

---

## Flujo único de ejecución — Verify

- ✅ Scheduler: `ura-maintenance-v2.timer` (activo, cada 6h)
- ❌ Timer antiguo: `ura-maintenance.timer` (desactivado, removido)
- ❌ Timer huérfano: `tuneladora-mantenimiento.timer` (dead symlink, not-found)
- ❌ Timer huérfano: `tuneladora-mantenimiento-semanal.timer` (dead symlink, not-found)
- ✅ Tuneladora mantenimiento: `scripts/pro/tuneladora_mantenimiento.py` (130 líneas)
- ✅ Tuneladora mejora: `scripts/pro/tuneladora_mejora.py` (85 líneas)
- ✅ Pipeline refactor: `scripts/pro/pipeline_refactor.py` (invocable desde mejora)
- ✅ Workers: `worker_manager.py` + `refactor_worker.py`
- ✅ Motor compartido: `scripts/pro/tuneladora/` (5 módulos + 4 plugins)
- ✅ SnapshotService: adaptador a `openclaw_firmador.delta_snapshot`
- ✅ Logger: único, funcional (archivo + stdout)
- ✅ Config: única (`Configuration` class)
- ✅ CLI actualizado: `motor/cli/cmd_ura.py` → apunta a nueva tuneladora

## Componentes eliminados

| Archivo | Líneas | Motivo |
|---------|--------|--------|
| `tuneladora_master.py` | 237 | Reemplazado por pipeline_refactor.py |
| `launch_refactor_gx10.sh` | 129 | Reemplazado por WorkerManager + RefactorWorker |
| `ura-maintenance.timer` | — | Reemplazado por ura-maintenance-v2.timer |

## Componentes conservados (no migrados)

| Archivo | Motivo |
|---------|--------|
| `mantenimiento/ura_maintenance.py` | Plan de reversión (conservar 1-2 ciclos) |
| `mantenimiento/ura_maintenance_remote.py` | Dependencia remota, evaluar migración futura |

## Conclusión

**La migración a Tuneladoras v2 está completa.**

- Un único scheduler systemd activo
- Dos tuneladoras con motor compartido
- Un pipeline de refactorización independiente
- Workers gestionados desde Python (sin shell scripts)
- Logger funcional (sin sistemas rotos)
- Configuración única
- 0 caminos alternativos activos
- 0 timers obsoletos activos
- 2 archivos de reversión conservados temporalmente

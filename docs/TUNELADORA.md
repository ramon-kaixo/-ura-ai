# Tuneladora v2.5 — URA AI

## Arquitectura

```
PipelineEngine (scripts/pro/tuneladora/engine.py)
├── run_script(script, args)  → CompletedProcess
├── run_ruff(args)            → CompletedProcess
├── run_git(args)             → CompletedProcess
├── run_plugins(plugins)      → dict (paralelo o secuencial)
├── health_ollama()           → list[models]
├── health_disk()             → dict[libre_gb]
├── notify(severity, title)   → None
├── report(title, data)       → None
├── set_dry_run(bool)         → None
│
├── ledger.py     — ExecutionLedger (append-only)
├── checkpoint.py — CheckpointManager (reanudacion)
├── scheduler.py   — TuneladoraScheduler (asincrono)
├── detector.py    — ProactiveDetector (disco, ram, ollama, git)
│
└── plugins/
    ├── code_quality.py — ruff check/fix/format
    ├── health.py       — system health checks
    ├── cleanup.py      — disk cleanup, forensic
    ├── arq_check.py    — ARQ architecture audit
    └── reporting.py    — state persistence
```

## Metricas Prometheus

| Metrica | Tipo | Labels |
|---------|------|--------|
| `tuneladora_executions_total` | Counter | plugin, status |
| `tuneladora_execution_duration_seconds` | Histogram | plugin |
| `tuneladora_plugins_active` | Gauge | — |
| `tuneladora_disk_free_gb` | Gauge | — |

Activar con `PROMETHEUS_ENABLED=true` en entorno.

## Como anadir un plugin nuevo

1. Crear archivo `scripts/pro/tuneladora/plugins/mi_plugin.py`
2. Definir clase con `__init__(self, engine: PipelineEngine)`
3. Anadir metodos que retornen dict
4. Registrar en `plugins/__init__.py`
5. Usar desde `tuneladora_mantenimiento.py`

## Como configurar pipelines

```python
from scripts.pro.tuneladora.scheduler import TuneladoraScheduler
s = TuneladoraScheduler()
s.add_pipeline("health", interval_minutes=5, auto_execute_safe=True)
s.add_pipeline("cleanup", interval_minutes=60, auto_execute_safe=True)
s.add_pipeline("audit", interval_minutes=360, auto_execute_safe=False)
s.start()
```

## Dry Run

```python
engine = PipelineEngine()
engine.set_dry_run(True)
# Simula ejecucion sin modificar nada
engine.run_script("scripts/pro/cleanup_logs.py")
```

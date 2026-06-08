# `core/sandbox_orchestrator.py`

- **Language:** python
- **Chunks:** 4

## Symbols

### class: `SandboxOrchestrator`
- Line: 99

class SandboxOrchestrator:
Orquestador de los 4 sandboxes — ciclo cada 6h.
Methods: __init__, _ensure_dirs, _load_log, _save_log, _load_state, _save_state, lock_sandbox, release_sandbox, get_sandbox_status, get_all_status, _run_sandbox, _tarea_generica, _check_tool, _get_current_rotation, _run_full_pipeline, run_normal_cycle, run_accelerated_cycle, trigger_accelerated_cycle, check_and_update_cycle, register_critical_change, get_failing_sandboxes, _ejecutar

### function: `get_sandbox_orchestrator`
- Line: 391

def get_sandbox_orchestrator():

## Module Overview

Módulo: core/sandbox_orchestrator.py
Propósito: Orquesta ejecuciones en sandbox: gestiona cola de tareas, log de ejecuciones y rotación de entornos.
Dependencias principales: json, datetime, pathlib, Sandbox
Reglas especiales: Máximo de ejecuciones concurrentes. Rotar logs cada 1000 entradas.

## Imports

```
datetime.datetime
datetime.timezone
json
logging
pathlib.Path
subprocess
threading
time
```

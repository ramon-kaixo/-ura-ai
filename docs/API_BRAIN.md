# Brain API — URA AI

## AutoMaintainer

```python
from motor.brain.auto_maintain import AutoMaintainer
from motor.brain.executor import ProposalExecutor
from motor.brain.observer import BrainObserver

m = AutoMaintainer(BrainObserver(), ProposalExecutor())
```

### Metodos publicos

| Metodo | Returns | Descripcion |
|--------|---------|-------------|
| `scan()` | `list[MaintenanceProposal]` | Escanea alertas, clasifica riesgo |
| `propose_and_maybe_execute()` | `list[dict]` | A2: ejecuta safe, propone medium/critical |
| `approve_and_execute(proposal, approved)` | `dict` | A1: ejecuta si approved=True |
| `start_scheduler()` | `None` | A3: inicia pipelines periodicos |
| `stop_scheduler()` | `None` | A3: detiene scheduler |
| `get_scheduler_status()` | `dict` | A3: running, pipelines, next_run |
| `auto_fix_code(target_dir)` | `dict` | A3: ruff fix + format + commit |
| `get_pending()` | `list` | Propuestas pendientes |
| `get_resolved(limit)` | `list` | Historial de ejecuciones |

### Ejemplo: A1

```python
m = AutoMaintainer(BrainObserver(), ProposalExecutor())
proposals = m.scan()
if proposals:
    result = m.approve_and_execute(proposals[0], approved=True)
    print(result.get("status"))
```

### Ejemplo: A2 autofix

```python
results = m.propose_and_maybe_execute()
for r in results:
    if r.get("auto_executed"):
        print(f"Auto-ejecutado: {r['verification']}")
```

### Ejemplo: A3 scheduler

```python
m.start_scheduler()
status = m.get_scheduler_status()
print(f"Running: {status['running']}, pipelines: {status['pipeline_count']}")
```

## BrainObserver

```python
from motor.brain.observer import BrainObserver

obs = BrainObserver()
obs.register_provider("disk", lambda: {"libre_gb": 100})
results = obs.observe_all()
```

### Eventos emitidos

- `HealthObservation(subsystem, status, latency, anomaly)`
- Proveedores registrados: disk, ollama

## AlertEngine

```python
from motor.brain.alerts import AlertEngine
from motor.brain.observer import BrainObserver

engine = AlertEngine(BrainObserver())
alerts = engine.evaluate()
```

### Tipos de alerta

| Patron | Severidad | Cuando |
|--------|-----------|--------|
| Provider caido | critical | status == "error" |
| DISCO CRITICO | emergency | < 10GB |
| Disco bajo | warning | < 50GB |
| Degradacion multiple | critical | ≥2 lentos + ≥1 error |
| Latencia red | warning | latencia > 500ms sin errores |

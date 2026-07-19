# F29 B4 — Runbook de Operación

## Graceful Shutdown

### F26 Memory
```python
from motor.memory import Memory
memory = Memory()
memory.shutdown(timeout=30)  # flush journal + save snapshot
```

### F27 Scheduler  
```python
from motor.agents.scheduler import AgentScheduler
scheduler = AgentScheduler()
results = scheduler.shutdown(timeout=30)  # drain queue, return pending results
```

## Health Endpoints

| Endpoint | Descripción | Implementación |
|----------|-------------|----------------|
| `GET /health` | Estado agregado + subsistemas | `HealthAggregator.health()` |
| `GET /ready` | Todos los subsistemas listos | `HealthAggregator.readiness()` |
| `GET /live` | Alive check simple | `HealthAggregator.liveness()` |

Registro de probes (ya implementado en F29 B1):
```python
from motor.platform.health import register_f24_f28_health_probes
register_f24_f28_health_probes()
```

## Backup / Restore

### Backup manual
```bash
python3 scripts/pro/backup_f26_memory.py backup --path /opt/ura/backups/memory_$(date +%s).json
```

### Restore manual
```bash
python3 scripts/pro/backup_f26_memory.py restore --path /opt/ura/backups/memory_1234567890.json
```

### Timer diario (systemd)
```ini
# /etc/systemd/system/ura-backup.timer
[Unit]
Description=URA daily memory backup

[Timer]
OnCalendar=daily
Persistent=true

[Install]
WantedBy=timers.target
```

## Configuración por Entorno

| Variable | Dev | Staging | Prod |
|----------|-----|---------|------|
| `URA_LOG_LEVEL` | DEBUG | INFO | WARN |
| `URA_LOG_STRUCTURED` | false | true | true |
| `URA_MEMORY_BACKUP_PATH` | /tmp | /opt/ura/backups | /opt/ura/backups |

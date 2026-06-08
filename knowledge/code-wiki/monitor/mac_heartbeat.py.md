# `monitor/mac_heartbeat.py`

- **Language:** python
- **Chunks:** 5

## Symbols

### class: `MacHeartbeat`
- Line: 27

class MacHeartbeat:
Verifica si Mac es alcanzable via ping.
Methods: __init__, _load_state, _save_state, check_mac, get_consecutive_failures, should_escalate, is_mac_connected, get_sync_command, get_status

### function: `check`
- Line: 131

def check():
Función de conveniencia: verifica Mac y retorna True si responde.

### function: `is_connected`
- Line: 136

def is_connected():
Función de conveniencia: True si Mac está conectada.

## Module Overview

Mac Heartbeat — Detección de presencia Mac.

Hace ping a Mac cada 30s. Si falla 3 veces consecutivas → alerta.
Información persistida en ~/.ura/run/ura_mac_heartbeat.json.

## Imports

```
datetime.datetime
json
os
pathlib.Path
subprocess
```

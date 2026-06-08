# `mantenimiento/ura_maintenance_remote.py`

- **Language:** python
- **Chunks:** 8

## Symbols

### function: `load_config`
- Line: 23

def load_config(config_path):
Cargar configuración desde archivo

### function: `validate_ip`
- Line: 58

def validate_ip(ip):
Validar formato de dirección IP

### function: `validate_ssh_user`
- Line: 67

def validate_ssh_user(user):
Validar nombre de usuario SSH

### function: `get_swarm_devices`
- Line: 74

def get_swarm_devices():
Obtener dispositivos del enjambre

### function: `run_remote_maintenance`
- Line: 98

def run_remote_maintenance(ip, user):
Ejecutar mantenimiento en nodo remoto de forma segura

### function: `main`
- Line: 207

def main():
Función principal

## Module Overview

URA Maintenance Remote - Ejecuta mantenimiento en nodos remotos del enjambre (SEGURE)

## Imports

```
datetime.datetime
json
logging
pathlib.Path
re
subprocess
sys
typing.Dict
typing.List
typing.Optional
```

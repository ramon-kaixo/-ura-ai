# `monitor/snc.py`

- **Language:** python
- **Chunks:** 12

## Symbols

### function: `load_runbook`
- Line: 60

def load_runbook():

### function: `run_command`
- Line: 73

def run_command(cmd, timeout):
Ejecuta un comando. Usa shell=True solo si hay operadores shell.
Excepción documentada: los comandos vienen del runbook whitelist (no input usuario).

### function: `check_service`
- Line: 96

def check_service(check_cmd):
Verifica un servicio ejecutando su comando de check.

### function: `is_command_forbidden`
- Line: 104

def is_command_forbidden(cmd, forbidden):
Verifica que un comando no esté en la lista prohibida.

### function: `repair_service`
- Line: 110

def repair_service(service_name, config, runbook):
Intenta reparar un servicio. Retorna 'ok', 'failed', 'escalated'.

### function: `check_mac_unauthorized_writes`
- Line: 140

def check_mac_unauthorized_writes():
Detecta intentos de escritura no autorizados en Mac.
Retorna True si detecta actividad sospechosa.

### function: `poll_services`
- Line: 175

def poll_services(runbook):
Polling de todos los servicios. Retorna dict de estado.
Modo Soberanía: GX10 opera independientemente.

### function: `write_state`
- Line: 291

def write_state(state):
Escribe el estado en /tmp/ura_snc_state.json de forma atómica.

### function: `handle_signal`
- Line: 306

def handle_signal(sig, frame):

### function: `main`
- Line: 313

def main():

## Module Overview

Sistema Nervioso Central (SNC) — Polling activo cada 10s.
Monitoriza procesos vía HTTP/socket, escribe estado en ~/.ura/run/ura_snc_state.json.
Ejecuta emergency_runbook.json ante fallos. Autónomo, sin dependencia de red.
Incluye: error_logger (log circular), mac_heartbeat (detección Mac).
Modo Soberanía: GX10 opera independientemente del Mac.

## Imports

```
datetime.datetime
error_logger.ErrorLogger
json
mac_heartbeat.MacHeartbeat
os
pathlib.Path
platform
shlex
signal
subprocess
sys
time
```

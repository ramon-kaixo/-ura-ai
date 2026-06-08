# `monitor/openclaw.py`

- **Language:** python
- **Chunks:** 13

## Symbols

### function: `load_runbook`
- Line: 57

def load_runbook():
Carga el runbook de emergencia. Solo intérprete, no decide.

### function: `load_state`
- Line: 65

def load_state():
Lee el state file escrito por snc.py. No lee estados legacy.

### function: `save_stats`
- Line: 75

def save_stats():
Registra stats en stats.json (Perfil A de memoria).

### function: `is_emergency`
- Line: 86

def is_emergency(state):
Determina si el estado del sistema es una emergencia.

### function: `is_forbidden`
- Line: 91

def is_forbidden(cmd, forbidden):
Verifica que un comando no esté en la lista prohibida.

### function: `run_command`
- Line: 97

def run_command(cmd, timeout):
Ejecuta un comando de forma segura sin shell=True.
Retorna (éxito, output).

### function: `request_human_confirmation`
- Line: 113

def request_human_confirmation(reason):
Solicita confirmación humana via claw_listener en Mac.
Retorna True si confirmado, False si cancelado o timeout.

### function: `execute_runbook_action`
- Line: 138

def execute_runbook_action(service_name, action, runbook):
Ejecuta una acción del runbook. Solo intérprete, no decide.
Retorna 'ok', 'blocked', 'failed', 'no_human_confirm'.

### function: `process_emergency`
- Line: 180

def process_emergency(state, runbook):
Procesa una emergencia: ejecuta runbook para servicios caídos.
NO toma decisiones propias. Solo interpreta el runbook.

### function: `handle_signal`
- Line: 202

def handle_signal(sig, frame):
Manejo de señales para cierre limpio.

### function: `main`
- Line: 209

def main():
Loop principal: lee state file, activa en emergencia, ejecuta runbook.

## Module Overview

OpenClaw — Brazo ejecutor de emergencia bajo control del SNC.

NO es un agente autónomo. Es un intérprete del emergency_runbook.json.
Solo se activa cuando snc.py marca STATE_EMERGENCY.
Si una incidencia no está en el runbook → bloqueo + ALERTA al administrador.

Protocolo de "Hombre Muerto": timeout de 60s sin confirmación humana
→ no ejecuta acciones destructivas por defecto.

Lee estado de: /tmp/ura_snc_state.json (escrito por snc.py)
Registra acciones en: stats.json (Perfil A de memoria)

## Imports

```
datetime.datetime
json
os
pathlib.Path
shlex
signal
subprocess
sys
time
```

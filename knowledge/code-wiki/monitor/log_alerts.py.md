# `monitor/log_alerts.py`

- **Language:** python
- **Chunks:** 8

## Symbols

### function: `ssh_run`
- Line: 31

def ssh_run(cmd):

### function: `load_seen_hashes`
- Line: 43

def load_seen_hashes():

### function: `save_seen_hashes`
- Line: 52

def save_seen_hashes(hashes):

### function: `hash_line`
- Line: 58

def hash_line(line):
Hash normalizado: ignora timestamp, solo contenido semántico.

### function: `fetch_critical_logs`
- Line: 67

def fetch_critical_logs():

### function: `main`
- Line: 83

def main():

## Module Overview

Log Alerts v2 — Centraliza y de-duplica errores críticos desde GX10.
Usa hash de contenido para no reportar el mismo error dos veces.

## Imports

```
collections.Counter
core.config_manager.CONFIG
datetime.datetime
hashlib
json
pathlib.Path
subprocess
sys
```

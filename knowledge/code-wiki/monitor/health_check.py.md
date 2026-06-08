# `monitor/health_check.py`

- **Language:** python
- **Chunks:** 10

## Symbols

### function: `ssh_run`
- Line: 29

def ssh_run(cmd):

### function: `measure_ssh_latency`
- Line: 41

def measure_ssh_latency():
Mide latencia SSH en ms.

### function: `measure_http_latency`
- Line: 55

def measure_http_latency():
Mide latencia HTTP Ollama en ms.

### function: `check_disk`
- Line: 69

def check_disk():

### function: `check_ram`
- Line: 105

def check_ram():

### function: `check_load`
- Line: 134

def check_load():

### function: `check_ollama_models`
- Line: 150

def check_ollama_models():

### function: `main`
- Line: 163

def main():

## Module Overview

Health Check v2 — Diagnóstico completo del GX10.
Mide: disco, RAM, carga CPU, VRAM Ollama, latencia SSH/HTTP.

## Imports

```
core.config_manager.CONFIG
datetime.datetime
pathlib.Path
subprocess
sys
time
urllib.request
```

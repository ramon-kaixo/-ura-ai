# `scripts/pro/ejecutor_api.py`

- **Language:** python
- **Chunks:** 7

## Symbols

### class: `ExecutorHandler`
- Line: 93

class ExecutorHandler:
Methods: do_POST, do_GET, log_message

### function: `log_evento`
- Line: 20

def log_evento(evento, datos):
Registra evento en MCP Sync del Mac Mini.

### function: `leer_contexto`
- Line: 37

def leer_contexto():
Lee el contexto compartido Ura-OpenCode.

### function: `escribir_contexto`
- Line: 45

def escribir_contexto(ctx):
Escribe el contexto compartido.

### function: `ejecutar_tarea`
- Line: 52

def ejecutar_tarea(task_desc, target_files):
Ejecuta una tarea de desarrollo y actualiza el contexto.

## Module Overview

ejecutor_api.py — Endpoint de automatizacion remota para URA.
Recibe tareas de desarrollo de la Tuneladora y las ejecuta.
Puerto: 4096 (OpenCode).

## Imports

```
datetime.datetime
http.server.BaseHTTPRequestHandler
http.server.HTTPServer
json
os
subprocess
threading
urllib.request
```

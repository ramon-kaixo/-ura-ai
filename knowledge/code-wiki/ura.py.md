# `ura.py`

- **Language:** python
- **Chunks:** 18

## Symbols

### function: `_run`
- Line: 33

def _run(cmd, desc):

### function: `cmd_finalize`
- Line: 42

def cmd_finalize(args):

### function: `cmd_test`
- Line: 107

def cmd_test(args):

### function: `cmd_maintenance`
- Line: 131

def cmd_maintenance(args):
Mantenimiento: local con dry-run, remoto sin dry-run.

### function: `cmd_rotate`
- Line: 142

def cmd_rotate(args):

### function: `cmd_snc`
- Line: 146

def cmd_snc(args):
Estado del Sistema Nervioso Central — fetch desde GX10.

### function: `cmd_health`
- Line: 186

def cmd_health(args):

### function: `cmd_alerts`
- Line: 190

def cmd_alerts(args):

### function: `cmd_index`
- Line: 194

def cmd_index(args):
Indexar documentos en la memoria RAG.

### function: `cmd_ask`
- Line: 212

def cmd_ask(args):
Consulta RAG: busca en documentos y responde con contexto.

### function: `cmd_memory`
- Line: 224

def cmd_memory(args):
Estadisticas de la memoria RAG.

### function: `cmd_snapshot`
- Line: 237

def cmd_snapshot(args):
Guardar snapshot del estado del repo.

### function: `cmd_doctor`
- Line: 260

def cmd_doctor(args):
Diagnóstico completo del sistema.

### function: `cmd_metrics`
- Line: 310

def cmd_metrics(args):
Métricas del router: modelos, latencia, cache.

### function: `cmd_status`
- Line: 328

def cmd_status(args):
Dashboard unificado — lee del SNC state file.

### function: `main`
- Line: 370

def main():

## Module Overview

URA CLI — Punto de entrada central del sistema.
Comandos: finalize, test, status, clean.

## Imports

```
contextlib
core.config_manager.CONFIG
core.config_manager.validate_config
core.config_manager.validate_schema
core.memory_engine.load_manifest
datetime.datetime
json
pathlib.Path
shlex
subprocess
sys
time
urllib.request
```

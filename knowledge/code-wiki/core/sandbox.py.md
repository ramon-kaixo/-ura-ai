# `core/sandbox.py`

- **Language:** python
- **Chunks:** 4

## Symbols

### class: `Sandbox`
- Line: 22

class Sandbox:
Caja de arena para pruebas aisladas de módulos.
Methods: __init__, _log, safe_import, create_backup, rollback, cleanup_old_backups

### function: `get_sandbox`
- Line: 220

def get_sandbox():
Obtener el singleton del sandbox.

## Module Overview

Módulo: core/sandbox.py
Propósito: Entorno aislado para ejecutar código Python de forma segura con import dinámico controlado.
Dependencias principales: importlib, subprocess, pathlib, logging
Reglas especiales: Nunca ejecutar código sin sandbox. Capturar OSError. No propagar excepciones del sandbox.

## Imports

```
asyncio
contextlib
datetime.datetime
importlib
logging
pathlib.Path
shutil
tempfile
```

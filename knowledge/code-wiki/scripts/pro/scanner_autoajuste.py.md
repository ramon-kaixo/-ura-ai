# `scripts/pro/scanner_autoajuste.py`

- **Language:** python
- **Chunks:** 7

## Symbols

### function: `snapshot`
- Line: 51

def snapshot(ruta):
Captura el estado del archivo antes de modificarlo.

Returns:
    {funciones, clases, imports, f821, tokens, hash, timestamp}

### function: `diff`
- Line: 121

def diff(entrada, salida):
Compara snapshot de entrada vs salida.

Returns:
    {paso, cambios, alertas, accion}

### function: `auto_ajustar`
- Line: 187

def auto_ajustar(ruta, intentos):
Intenta reparar errores deterministamente (sin LLM).

Returns:
    (reparado, [acciones_aplicadas])

### function: `escanear`
- Line: 236

def escanear(ruta):
Escanea entrada y salida del archivo.

Si ya existe snapshot previo (en .nervioso/), hace diff.
Si no, crea un snapshot nuevo.

### function: `scan_project`
- Line: 284

def scan_project():
Escanear todo el proyecto.

### function: `main`
- Line: 303

def main():

## Imports

```
argparse
ast
hashlib
json
os
pathlib.Path
subprocess
sys
time
```

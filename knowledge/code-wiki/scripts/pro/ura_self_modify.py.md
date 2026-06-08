# `scripts/pro/ura_self_modify.py`

- **Language:** python
- **Chunks:** 8

## Symbols

### function: `ejecutar_remoto`
- Line: 13

def ejecutar_remoto(python_code, env):
Ejecuta codigo Python en el contenedor Open WebUI del GX10.

### function: `leer_prompt`
- Line: 36

def leer_prompt():
Lee el system prompt actual de URA.

### function: `actualizar_prompt`
- Line: 51

def actualizar_prompt(nuevo_prompt):
Actualiza el system prompt de URA en Open WebUI.

### function: `listar_tools`
- Line: 73

def listar_tools():
Lista las tools disponibles para URA.

### function: `crear_tool`
- Line: 87

def crear_tool(nombre, descripcion, codigo):
Crea una new tool en Open WebUI.

### function: `reiniciar`
- Line: 125

def reiniciar():
Reinicia Open WebUI para aplicar cambios.

## Module Overview

ura_self_modify.py — Permite a URA modificar su propio prompt y tools.
Ejecuta contra la BD de Open WebUI en el GX10.

## Imports

```
json
pathlib.Path
subprocess
sys
tempfile
time
```

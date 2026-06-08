# `agents/agente_sandbox_codigo.py`

- **Language:** python
- **Chunks:** 15

## Symbols

### function: `pushover`
- Line: 54

def pushover(msg, title, pri):

### function: `md5`
- Line: 75

def md5(ruta):

### function: `es_critico`
- Line: 83

def es_critico(rel):

### function: `cargar_inventario`
- Line: 96

def cargar_inventario():

### function: `actualizar_inventario`
- Line: 100

def actualizar_inventario(rel, h, ver):

### function: `create_branch`
- Line: 116

def create_branch(rel, v_old, v_new, origin, reason):

### function: `test_file`
- Line: 137

def test_file(file_path):

### function: `_probar_compilacion`
- Line: 150

def _probar_compilacion(pruebas_path):

### function: `_rechazar_cambio`
- Line: 155

def _rechazar_cambio(pruebas_path, archivo, rel, err):

### function: `_esperar_aprobacion`
- Line: 161

def _esperar_aprobacion(pruebas_path, archivo, rel):

### function: `_aprobar_cambio`
- Line: 167

def _aprobar_cambio(pruebas_path, archivo, rel):

### function: `_procesar_aprobados`
- Line: 172

def _procesar_aprobados():

### function: `main`
- Line: 198

def main():

## Module Overview

agente_sandbox_codigo.py — Vigilante del sandbox de codigo URA.

Modo mixto:
- AUTONOMO en lo aburrido (mover, testear, documentar)
- MANUAL en lo critico (Ramon aprueba antes de tocar produccion)

## Imports

```
datetime.datetime
hashlib
json
logging
os
pathlib.Path
requests
shutil
subprocess
time
```

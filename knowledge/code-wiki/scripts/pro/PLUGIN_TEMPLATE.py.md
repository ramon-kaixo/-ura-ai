# `scripts/pro/PLUGIN_TEMPLATE.py`

- **Language:** python
- **Chunks:** 6

## Symbols

### function: `log`
- Line: 41

def log(msg):

### function: `run`
- Line: 45

def run(cmd, timeout):

### function: `mi_logica`
- Line: 53

def mi_logica(archivo):
Implementar la lógica del script aquí.

### function: `main`
- Line: 63

def main():

## Module Overview

PLUGIN_TEMPLATE — Copiar y modificar para crear un script nuevo.

PASOS:
  1. Copiar: cp PLUGIN_TEMPLATE.py mi_nuevo_script.py
  2. Editar: cambiar nombre, fase, timeout, args
  3. Implementar: escribir la lógica en main()
  4. Listo: tuneladora_mejora lo descubre solo

FASES DISPONIBLES:
  "pre"      — Antes del refactor (validación, snapshots)
  "refactor" — Durante el refactor (poda, transformación)
  "post"     — Después del refactor (validación, auto-reglas)
  "always"   — Se ejecuta siempre (independiente de fase)

## Imports

```
argparse
datetime.datetime
pathlib.Path
subprocess
```

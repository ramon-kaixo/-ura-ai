# `scripts/pro/alineador.py`

- **Language:** python
- **Chunks:** 8

## Symbols

### function: `log`
- Line: 24

def log(msg):

### function: `check_monologo`
- Line: 29

def check_monologo():
Verifica que el monologo tenga acciones reales, no charla.

### function: `check_deviation`
- Line: 63

def check_deviation(message):
Detecta si un mensaje se desvia del objetivo (contiene filosofia, opiniones, etc).

### function: `agregar_sugerencia`
- Line: 81

def agregar_sugerencia(problema, solucion):

### function: `scan_project`
- Line: 98

def scan_project():

### function: `main`
- Line: 104

def main():

## Module Overview

alineador.py — Valida que las respuestas de URA/OpenClaw sean utiles y no se desvien.
Se ejecuta en la tuneladora para auditar el comportamiento.

## Imports

```
argparse
datetime.datetime
json
pathlib.Path
```

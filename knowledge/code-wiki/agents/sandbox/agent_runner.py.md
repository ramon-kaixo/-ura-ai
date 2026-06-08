# `agents/sandbox/agent_runner.py`

- **Language:** python
- **Chunks:** 3

## Symbols

### function: `main`
- Line: 14

def main():

## Module Overview

agent_runner.py — Punto de entrada para agentes sandbox.

Cada agente recibe:
  --categoria : legal|diseno|programacion|hosteleria
  --input     : ruta al archivo .nervioso/ a procesar (solo lectura)
  --output    : ruta donde escribir resultados

El agente NO tiene red. NO puede escribir fuera de --output.

## Imports

```
argparse
json
pathlib.Path
sys
time
```

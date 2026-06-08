# `scripts/pro/analizar_fallo_conciencia.py`

- **Language:** python
- **Chunks:** 6

## Symbols

### function: `log`
- Line: 49

def log(mensaje):

### function: `agregar_sugerencia`
- Line: 54

def agregar_sugerencia(problema, solucion):

### function: `notificar`
- Line: 72

def notificar(mensaje):

### function: `diagnosticar_y_corregir`
- Line: 77

def diagnosticar_y_corregir():
Ejecuta el test, analiza fallos, intenta corregir.

## Module Overview

analizar_fallo_conciencia.py — Analiza resultados del test de conciencia
y ejecuta acciones correctivas automaticas.

Flujo:
1. Ejecuta test_conciencia.py
2. Si falla, determina la causa probable
3. Intenta corregirla (permisos, tools, system prompt)
4. Si no puede, notifica al instalador

## Imports

```
datetime.datetime
json
os
pathlib.Path
subprocess
sys
```

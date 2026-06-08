# `scripts/pro/watermark_aggregator.py`

- **Language:** python
- **Chunks:** 11

## Symbols

### function: `cargar`
- Line: 35

def cargar():

### function: `guardar`
- Line: 41

def guardar(data):

### function: `detectar_patrones`
- Line: 46

def detectar_patrones(data, umbral):
Detecta errores que aparecen ≥umbral veces (patrón sistémico).

### function: `_diagnosticar`
- Line: 80

def _diagnosticar(tipo):

### function: `marcar_reparado`
- Line: 95

def marcar_reparado(watermark_id):

### function: `limpiar_resueltos`
- Line: 106

def limpiar_resueltos():
Elimina watermarks reparados que tienen más de 7 días.

### function: `estado`
- Line: 125

def estado():

### function: `scan_project`
- Line: 142

def scan_project():

### function: `main`
- Line: 148

def main():

## Module Overview

Agregador de Watermarks — Detecta patrones sistémicos y gestiona incidencias.

Lee watermarks del pipeline, detecta errores que se repiten ≥3 ciclos,
genera reglas de reparación automática (auto_reglas.py), y escala a
diagnóstico de prompt engineering.

Uso:
  python3 watermark_aggregator.py                          # Ver estado
  python3 watermark_aggregator.py --marcar-reparado <id>   # Marcar watermark como reparado
  python3 watermark_aggregator.py --limpiar                 # Limpiar watermarks resueltos
  python3 watermark_aggregator.py --auto-reglas             # Estado + generar reglas

## Imports

```
argparse
collections.Counter
contextlib
json
os
pathlib.Path
subprocess
time
```

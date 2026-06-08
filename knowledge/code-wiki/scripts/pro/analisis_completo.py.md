# `scripts/pro/analisis_completo.py`

- **Language:** python
- **Chunks:** 10

## Symbols

### function: `log`
- Line: 40

def log(msg):

### function: `llm`
- Line: 45

def llm(prompt, model):

### function: `recopilar_estado`
- Line: 65

def recopilar_estado():

### function: `analizar_monologo`
- Line: 96

def analizar_monologo():

### function: `reflexionar_acciones`
- Line: 127

def reflexionar_acciones():

### function: `guardar_sugerencia`
- Line: 156

def guardar_sugerencia(analisis):

### function: `scan_project`
- Line: 172

def scan_project():

### function: `main`
- Line: 178

def main():

## Module Overview

analisis_completo.py — Analisis integral de URA (estado + monologo + acciones).

FUSIONADO CON:
  - analisis_llm.py (analisis de estado del sistema con LLM)
  - meta_mejora_v2.py (analisis de monologo interno)
  - reflexion_ura.py (reflexion sobre acciones)

## Imports

```
argparse
contextlib
datetime.datetime
json
os
pathlib.Path
subprocess
sys
time
urllib.request
```

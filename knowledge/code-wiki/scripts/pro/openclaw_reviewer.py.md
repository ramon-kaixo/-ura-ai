# `scripts/pro/openclaw_reviewer.py`

- **Language:** python
- **Chunks:** 7

## Symbols

### function: `llamar_ollama`
- Line: 29

def llamar_ollama(prompt, model, timeout):
Llama a Ollama con el modelo revisor.

### function: `revisar`
- Line: 49

def revisar(codigo_original, codigo_refactorizado, nombre_archivo):
Envía código al revisor q8_0 y obtiene veredicto.

Returns:
    {veredicto, razones, confianza, tiempo_s, modelo}

### function: `revisar_archivos`
- Line: 126

def revisar_archivos(ruta_original, ruta_refactorizado):
Revisa dos archivos: original vs refactorizado.

### function: `scan_project`
- Line: 138

def scan_project():

### function: `main`
- Line: 144

def main():

## Module Overview

OpenClaw Reviewer — Revisor Independiente con qwen2.5-coder:q8_0.

Uso:
  python3 openclaw_reviewer.py original.py refactorizado.py
  python3 openclaw_reviewer.py original.py refactorizado.py --json

## Imports

```
argparse
json
os
pathlib.Path
sys
time
urllib.request
```

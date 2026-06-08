# `scripts/pro/ajustar_contexto.py`

- **Language:** python
- **Chunks:** 8

## Symbols

### function: `estimar_tokens`
- Line: 21

def estimar_tokens(texto):
Estima tokens de forma conservative (promedio: 4 chars/token).

### function: `contar_lineas_codigo`
- Line: 28

def contar_lineas_codigo(texto):

### function: `ajustar_contexto`
- Line: 32

def ajustar_contexto(tokens_reales, max_modelo, factor_colchon, min_chunk):
Calcula el límite de contexto óptimo para el LLM.

Args:
    tokens_reales: Tokens estimados del fragmento.
    max_modelo: Máximo que soporta el modelo (ej: 100K).
    factor_colchon: Espacio extra para la respuesta (1.5 = 50%).
    min_chunk: Mínimo absoluto (no bajar de aquí).

Returns:
    Límite óptimo de tokens para enviar al LLM.

### function: `analizar_archivo`
- Line: 55

def analizar_archivo(ruta):
Analiza un archivo y devuelve metadata de contexto.

### function: `scan_project`
- Line: 73

def scan_project():

### function: `main`
- Line: 79

def main():

## Module Overview

Ajuste Dinámico de Contexto para Refactorización.

Calcula el contexto óptimo para el LLM según el tamaño del archivo.

## Imports

```
argparse
pathlib.Path
sys
```

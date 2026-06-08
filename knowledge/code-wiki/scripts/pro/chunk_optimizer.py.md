# `scripts/pro/chunk_optimizer.py`

- **Language:** python
- **Chunks:** 10

## Symbols

### function: `cargar`
- Line: 61

def cargar():

### function: `_nuevo`
- Line: 70

def _nuevo():

### function: `guardar`
- Line: 80

def guardar(data):

### function: `recomendar`
- Line: 85

def recomendar(modelo):
Devuelve el chunk recomendado según el histórico de errores.

### function: `ajustar`
- Line: 119

def ajustar(f821_delta, token_delta_pct, modelo):
Ajusta el chunk según la calidad del último refactor.

Args:
    f821_delta: Cambio en F821 (negativo = mejora, positivo = empeora)
    token_delta_pct: Divergencia de tokens en %

### function: `estado`
- Line: 198

def estado():
Devuelve el estado actual y la tendencia.

### function: `scan_project`
- Line: 223

def scan_project():

### function: `main`
- Line: 229

def main():

## Module Overview

Chunk Optimizer — Ajuste dinámico de tamaño según tasa de error.

Principio:
  Si el scanner muestra que el LLM produce buen código (F821 bajo),
  AUMENTAR el chunk → más código por llamada → menos llamadas → más rápido.

  Si el scanner muestra errores,
  REDUCIR el chunk → menos código → más precisión.

Es un bucle cerrado:
  Scanner SALIDA → mide calidad → Chunk Optimizer → ajusta tamaño → siguiente ciclo

Optimización GPU:
  Target: 70-80% del contexto del modelo.
  Si el modelo acepta 32K tokens y estamos usando 8K (25%), podemos subir a 22K.
  Más tokens por llamada = GPU más ocupada = menos overhead de llamadas.

  Con 107 funciones a 5K tokens cada una:    ~22 llamadas al LLM
  Con 107 funciones a 20K tokens cada una:   ~6 llamadas al LLM
  Ahorro potencial: ~70% menos llamadas.

Uso:
  python3 chunk_optimizer.py --estado           # Ver estado actual
  python3 chunk_optimizer.py --ajustar <f821_delta> <token_delta_pct>  # Ajustar
  python3 chunk_optimizer.py --recomendar <modelo>    # Recomendar tamaño

## Imports

```
argparse
json
os
pathlib.Path
time
```

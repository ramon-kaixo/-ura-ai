# `scripts/pro/token_screen.py`

- **Language:** python
- **Chunks:** 8

## Symbols

### function: `_free_ram_mb`
- Line: 50

def _free_ram_mb():
RAM libre en MB. psutil → /proc/meminfo → fallback 8GB.

### function: `estimar_tokens`
- Line: 67

def estimar_tokens(texto):
Estimación conservadora: ~4 chars por token.

### function: `ajustar_contexto`
- Line: 74

def ajustar_contexto(tokens_reales, modelo, factor, min_tokens):
Calcula el límite óptimo de contexto para el LLM.

### function: `_esperar_ram`
- Line: 84

def _esperar_ram(max_wait_s):
Espera hasta que haya RAM suficiente. False si timeout.

### function: `screen`
- Line: 94

def screen(codigo, modelo):
Verifica recursos y ajusta contexto. Bloquea si RAM insuficiente.

Edge cases:
- Código vacío/NULL → retorna ok=False inmediatamente
- psutil ausente → fallback a /proc/meminfo
- RAM temporalmente baja → espera hasta 5 min
- Modelo desconocido → usa límite default (32768)

### function: `scan_project`
- Line: 156

def scan_project():
Escanear todo el proyecto.

### function: `main`
- Line: 172

def main():

## Imports

```
argparse
pathlib.Path
psutil
sys
time
```

# `scripts/pro/pipeline_supremo.py`

- **Language:** python
- **Chunks:** 18

## Symbols

### function: `run_step`
- Line: 37

def run_step(cmd, timeout, json_output):

### function: `update_conciencia`
- Line: 47

def update_conciencia(proceso, estado, progreso):

### function: `step_guardian`
- Line: 61

def step_guardian():

### function: `step_token_screen`
- Line: 65

def step_token_screen(ruta):

### function: `step_scanner_entrada`
- Line: 74

def step_scanner_entrada(ruta):

### function: `step_poda`
- Line: 83

def step_poda(ruta):

### function: `step_refactor`
- Line: 92

def step_refactor():

### function: `step_compactadora`
- Line: 106

def step_compactadora(ruta, chromatic_map):

### function: `step_scanner_salida`
- Line: 124

def step_scanner_salida(ruta):

### function: `step_inspectores`
- Line: 134

def step_inspectores(ruta):

### function: `step_openclaw`
- Line: 143

def step_openclaw(ruta):

### function: `step_alineador`
- Line: 152

def step_alineador():

### function: `step_guardian_verify`
- Line: 159

def step_guardian_verify(archivo):

### function: `ejecutar`
- Line: 166

def ejecutar(ruta):

### function: `init_conciencia`
- Line: 225

def init_conciencia():

### function: `main`
- Line: 242

def main():

## Module Overview

Pipeline Supremo — Orquestador completo de refactorizacion URA.

FLUJO CORRECTO:
  0. Guardian disco (SHA-256 scan)
  1. Token screen (RAM check)
  2. Scanner entrada (snapshot AST)
  3. Poda mecanica (dead code + chromatic map)
  4. Refactor con compactacion (compacta -> LLM -> descompacta)
  5. Compactadora (reensamblaje + validacion AST/tokens/chromatic)
  6. Auto-reglas (reglas deterministas F821)
  7. Scanner salida (diff + chunk_optimizer bucle cerrado)
  8. Inspectores + OpenClaw (paralelo)
  9. Alineador (validacion de respuestas)
  10. Decision consenso (ESCRIBIR/WATERMARK/REPARAR/ROLLBACK)
  11. Guardian verify (post-escritura)

FUSIONADO CON:
  - alineador.py (validacion de calidad de respuestas URA/OpenClaw)

## Imports

```
argparse
concurrent.futures.ThreadPoolExecutor
json
pathlib.Path
subprocess
sys
time
```

# `scripts/pro/tuneladora_mejora.py`

- **Language:** python
- **Chunks:** 4

## Symbols

### function: `main`
- Line: 33

def main():

### function: `_guardar_reporte`
- Line: 91

def _guardar_reporte(reporte, t_inicio):

## Module Overview

TUNELADORA DE MEJORA CONTINUA — Sistema auto-descubrible.

FLUJO AUTOMÁTICO (descubre scripts via plugin_registry):
  Fase "pre":     Validación inicial (token_screen, scanner)
  Fase "refactor": Transformación de código (poda, refactor, watchdog)
  Fase "post":    Validación final (auto_reglas, inspectores)

AGREGAR SCRIPTS SIN EDITAR ESTE ARCHIVO:
  1. Copiar PLUGIN_TEMPLATE.py → mi_script.py
  2. Editar PLUGIN = {"name": ..., "phase": ..., "timeout": ...}
  3. Ejecutar: python3 tuneladora_mejora.py
  4. El script se ejecuta automáticamente en su fase

## Imports

```
datetime.datetime
json
os
pathlib.Path
plugin_registry.discover_all
plugin_registry.list_plugins
plugin_registry.log
plugin_registry.run_phase
sys
time
```

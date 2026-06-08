# `core/error_sandbox.py`

- **Language:** python
- **Chunks:** 5

## Symbols

### class: `SandboxResult`
- Line: 28

class SandboxResult:
Resultado del análisis en sandbox.

### class: `ErrorSandbox`
- Line: 41

class ErrorSandbox:
Sandbox para análisis de errores no solucionados.
Methods: __init__, _load_config, _default_config, _load_knowledge_base, _default_knowledge_base, analyze_error, _generate_analysis, _attempt_solution, get_sandbox_log, get_manual_intervention_errors

### function: `main`
- Line: 250

def main():
Punto de entrada CLI.

## Module Overview

URA - Sandbox de Errores.

Sistema para errores que no se pudieron solucionar automáticamente:
- Análisis profundo del error
- Búsqueda de soluciones en base de conocimiento
- Ejecución de soluciones alternativas
- Reporte de resultados para intervención manual

## Imports

```
argparse
dataclasses.dataclass
datetime.datetime
json
logging
pathlib.Path
port_assigner.PortAssigner
subprocess
time
```

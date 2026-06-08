# `monitor/error_logger.py`

- **Language:** python
- **Chunks:** 5

## Symbols

### class: `ErrorLogger`
- Line: 26

class ErrorLogger:
Log circular de errores con rotación automática.
Methods: __init__, _generate_error_id, log_error, get_recent_errors, get_errors_by_severity, has_recent_critical, rotate_if_needed, count_errors, clear

### function: `log_error`
- Line: 135

def log_error(context, gateway_status, severity, message):
Función de conveniencia para logear errores.

### function: `get_recent`
- Line: 140

def get_recent(count):
Función de conveniencia para obtener errores recientes.

## Module Overview

Error Logger — Log circular de errores para URA.

Formato: JSON Lines (.jsonl)
Rotación: Máximo 1000 entradas, elimina las más antiguas.
Cada entrada: timestamp, error_id, context, gateway_status, severity, message.
Detecta plataforma automáticamente (Mac vs ASUS).

## Imports

```
contextlib.suppress
datetime.datetime
json
pathlib.Path
platform
time
uuid
```

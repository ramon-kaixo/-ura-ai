# `tests/test_integration.py`

- **Language:** python
- **Chunks:** 6

## Symbols

### function: `gx10_accessible`
- Line: 29

def gx10_accessible():
Verifica si GX10 es accesible vía SSH.

### function: `check`
- Line: 42

def check(desc, fn):

### function: `skip`
- Line: 53

def skip(desc):

### function: `main`
- Line: 58

def main():

## Module Overview

Integration Tests — URA v3.0
Flujos reales contra GX10. Condicionales: si GX10 no responde, se saltan.

## Imports

```
core.config_manager.CONFIG
json
pathlib.Path
subprocess
sys
urllib.request
```

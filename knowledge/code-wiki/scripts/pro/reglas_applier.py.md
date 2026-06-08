# `scripts/pro/reglas_applier.py`

- **Language:** python
- **Chunks:** 6

## Symbols

### function: `detectar_f821_en_codigo`
- Line: 11

def detectar_f821_en_codigo(codigo, archivo):
Detecta F821 en código usando ruff (rápido) o AST fallback.

### function: `_extraer_nombre_f821`
- Line: 40

def _extraer_nombre_f821(mensaje):
Extrae el nombre del símbolo no definido de un mensaje F821.

### function: `_es_import_estandar`
- Line: 46

def _es_import_estandar(nombre):

### function: `aplicar_regla_a_codigo`
- Line: 56

def aplicar_regla_a_codigo(codigo, regla):
Aplica una regla de reparación al código.

Returns:
    (codigo_reparado, aplicado_con_exito)

## Module Overview

Reglas Applier — Aplica reparaciones deterministas.

## Imports

```
json
os
pathlib.Path
re
subprocess
```

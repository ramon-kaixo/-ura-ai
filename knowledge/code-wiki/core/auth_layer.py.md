# `core/auth_layer.py`

- **Language:** python
- **Chunks:** 4

## Symbols

### function: `validate`
- Line: 12

def validate(api_key):
Valida una API key.

Args:
    api_key: La API key a validar (puede ser None)

Returns:
    True si la key es válida, False en caso contrario

### function: `require_auth`
- Line: 30

def require_auth():
Indica si la autenticación está habilitada.

Returns:
    True si se requiere autenticación, False en caso contrario

## Module Overview

Auth Layer - Validación de API keys para endpoints protegidos.

## Imports

```
os
typing.Optional
```

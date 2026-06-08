# `core/config_manager.py`

- **Language:** python
- **Chunks:** 12

## Symbols

### function: `_expand_paths`
- Line: 20

def _expand_paths(config):
Expande ~ a home directory en todos los paths del perfil.

### function: `_load_raw_config`
- Line: 38

def _load_raw_config():
Carga el archivo JSON de configuración.

### function: `load_config`
- Line: 44

def load_config():
Carga y fusiona la configuración para el sistema operativo actual.

### function: `get_base_dir`
- Line: 72

def get_base_dir():
Devuelve el directorio base URA según el SO: ~/URA en Mac, /home/ramon/URA en Linux.

### function: `get_ollama_url`
- Line: 77

def get_ollama_url():
Devuelve la URL completa de Ollama para este nodo.

### function: `get_role`
- Line: 82

def get_role():
Devuelve el rol de este nodo: 'client' o 'server'.

### function: `get_hostname`
- Line: 87

def get_hostname():
Devuelve el hostname lógico de este nodo según el perfil.

### function: `validate_config`
- Line: 92

def validate_config():
Valida que los directorios declarados en config existan y tengan permisos.
Retorna lista de warnings.

### function: `validate_schema`
- Line: 128

def validate_schema():
Valida la estructura de CONFIG contra el esquema esperado.
Retorna lista de errores (vacia = OK).

### function: `validate_schema_json`
- Line: 154

def validate_schema_json():
Valida system_config.json contra el JSON Schema declarativo (config/schema.json).
Requiere jsonschema instalado. Si no está, retorna lista vacía (no bloquea).

## Module Overview

Config Manager - Carga unificada de configuración con perfiles por sistema operativo.
Detecta automáticamente Linux (Asus GX10) vs Darwin (Mac) y carga el perfil correcto.

## Imports

```
json
jsonschema
os
pathlib.Path
platform
typing.Any
```

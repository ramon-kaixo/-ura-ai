# `mantenimiento/ura_maintenance.py`

- **Language:** python
- **Chunks:** 10

## Symbols

### class: `SecurityValidator`
- Line: 95

class SecurityValidator:
Validador de seguridad para operaciones de archivo
Methods: __init__, is_safe_to_delete, _matches_exclude_pattern, _is_in_allowed_dir

### class: `MaintenanceConfig`
- Line: 147

class MaintenanceConfig:
Configuración de mantenimiento
Methods: __init__

### class: `SystemCleaner`
- Line: 157

class SystemCleaner:
Clase base para limpieza de sistemas
Methods: __init__, get_disk_usage, should_clean, record_operation, safe_remove, safe_rmtree

### class: `LinuxCleaner`
- Line: 223

class LinuxCleaner:
Limpiador específico para Linux
Methods: __init__, clean_docker, clean_apt_cache, clean_pip_cache, clean_old_logs, clean_temp_files

### class: `MacCleaner`
- Line: 402

class MacCleaner:
Limpiador específico para macOS
Methods: __init__, clean_docker, clean_brew_cache, clean_pip_cache, clean_application_caches, clean_logs

### class: `MaintenanceOrchestrator`
- Line: 574

class MaintenanceOrchestrator:
Orquestador de mantenimiento para el enjambre
Methods: __init__, _get_cleaner, run_maintenance, _save_results

### function: `load_config`
- Line: 53

def load_config(config_path):
Cargar configuración desde archivo

### function: `main`
- Line: 645

def main():
Función principal

## Module Overview

URA Maintenance System - Sistema de mantenimiento automatizado (SEGURE)
Escanea y limpia sistemas del enjambre URA de forma segura

## Imports

```
datetime.datetime
fnmatch.fnmatch
grp
json
logging
os
pathlib.Path
platform
pwd
re
shutil
subprocess
sys
typing.Dict
typing.List
typing.Optional
typing.Tuple
```

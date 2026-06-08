# `tests/test_unit.py`

- **Language:** python
- **Chunks:** 3

## Symbols

### function: `check`
- Line: 20

def check(desc, expr):

## Module Overview

Unit Test Suite — URA v3.0
Verifica que nada de lo de "ayer" vuelva a pasar:
- Todos los módulos importan sin crash
- Todas las funciones aceptan los argumentos correctos
- La config carga y tiene estructura válida
- Las funciones de clasificación y ruteo devuelven tipos correctos.

## Imports

```
core.config_manager.CONFIG
core.config_manager.get_base_dir
core.config_manager.get_hostname
core.config_manager.get_ollama_url
core.config_manager.get_role
core.config_manager.validate_config
core.config_manager.validate_schema
core.memory_engine.MANIFEST_PATH
core.memory_engine._chromadb_available
core.memory_engine._chunk_text
core.memory_engine._sha256
core.memory_engine.load_manifest
core.memory_engine.rag_enabled
core.memory_engine.save_manifest
core.model_router.MetricsCollector
core.model_router.PromptCache
core.model_router.clasificar_peticion
core.model_router.obtener_modelos_disponibles
core.model_router.seleccionar_modelo
json
mantenimiento.ura_maintenance.MaintenanceConfig
mantenimiento.ura_maintenance.SecurityValidator
mantenimiento.ura_maintenance_remote.validate_ip
mantenimiento.ura_maintenance_remote.validate_ssh_user
monitor.health_check.measure_http_latency
monitor.health_check.measure_ssh_latency
monitor.log_alerts.hash_line
monitor.log_alerts.load_seen_hashes
monitor.log_alerts.save_seen_hashes
monitor.snc
monitor.snc.CRITICAL_TIMEOUT
monitor.snc.POLL_INTERVAL
monitor.snc.RUNBOOK_PATH
monitor.snc.STATE_FILE
monitor.snc.check_service
monitor.snc.is_command_forbidden
monitor.snc.load_runbook
monitor.snc.repair_attempts
monitor.snc.write_state
monitor.snc_remote._escape_applescript
os
pathlib.Path
shlex
shutil
sys
tempfile
yaml
```

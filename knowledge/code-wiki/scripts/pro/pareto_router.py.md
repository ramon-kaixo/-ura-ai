# `scripts/pro/pareto_router.py`

- **Language:** python
- **Chunks:** 8

## Symbols

### function: `_free_ram_mb`
- Line: 61

def _free_ram_mb():

### function: `sync_criticos`
- Line: 74

def sync_criticos():
Sincroniza los datos del 20% crítico a Mac y Hetzner.

### function: `check_ram_purge`
- Line: 124

def check_ram_purge():
Si RAM >85%, purgar caché de datos pesados.

### function: `clasificar_datos`
- Line: 148

def clasificar_datos():
Clasifica todos los datos del pipeline en 20% crítico vs 80% pesado.

### function: `scan_project`
- Line: 167

def scan_project():

### function: `main`
- Line: 173

def main():

## Module Overview

Pareto Router — Distribución 20/80 de datos en el ecosistema URA.

📖 MANUAL DE USO RÁPIDO:
  python3 scripts/pro/pareto_router.py --clasificar    # Clasificar datos del pipeline
  python3 scripts/pro/pareto_router.py --sync-criticos  # Sincronizar 20% crítico a Mac+Hetzner
  python3 scripts/pro/pareto_router.py --purge-cache    # Purgar caché si RAM >85%

🔒 PRINCIPIO 20/80:
  ASUS (128GB RAM): 100% IA pesada (Ollama) + 100% análisis vídeo
  Solo 20% datos críticos → sincronizar al exterior (alertas, conciencia, reglas)
  80% datos pesados → cache local ASUS o Hetzner (backups, logs, snapshots, vídeo)
  DERP relays: PROHIBIDOS para ASUS→Hetzner. Forzar conexión directa.

## Imports

```
argparse
json
os
pathlib.Path
psutil
subprocess
sys
time
```

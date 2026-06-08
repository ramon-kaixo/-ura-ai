# `core/ura_sandbox_bridge.py`

- **Language:** python
- **Chunks:** 6

## Symbols

### class: `SandboxConfig`
- Line: 52

class SandboxConfig:
Methods: from_env, to_dict

### class: `SandboxBridge`
- Line: 81

class SandboxBridge:
Capa de aislamiento de I/O. Hoy passthrough; el día de la VM, swap automático.
Methods: __init__, is_isolated, info

### function: `get_sandbox`
- Line: 240

def get_sandbox():

### function: `reset_sandbox`
- Line: 247

def reset_sandbox():
Forzar reinicialización (tras cambiar URA_SANDBOX_MODE).

## Module Overview

URA Sandbox Bridge — Capa de seguridad para todo I/O de internet (Fase 3).

Objetivo: cuando el usuario instale el "ordenador virtual" (VM/contenedor),
todas las descargas, fetches y ejecuciones de OpenClaw pasarán por esa VM.
Hoy no hay VM disponible, así que el bridge funciona en modo `passthrough`.

Modos:
  - "passthrough"  → ejecuta directamente en el host (modo actual)
  - "ssh"          → ejecuta en VM remota vía SSH (cuando esté lista)
  - "lima"         → ejecuta dentro de Lima (https://lima-vm.io) — alternativa Mac sin Docker

Configuración por env vars:
  URA_SANDBOX_MODE        passthrough|ssh|lima
  URA_SANDBOX_SSH_HOST    user@host
  URA_SANDBOX_SSH_KEY     ruta a clave privada
  URA_SANDBOX_LIMA_NAME   nombre de la instancia lima

API estable (no cambia entre modos):

    bridge = get_sandbox()
    text, final_url = await bridge.fetch_page(url)
    output           = await bridge.run_command(["curl", "-s", url])
    payload          = await bridge.run_openclaw(tema)

El día que instales la VM, sólo necesitas exportar URA_SANDBOX_MODE=ssh
(o lima) y el resto del código no cambia.

## Imports

```
__future__.annotations
asyncio
core.stealth_fetcher.fetch_page
core.ura_openclaw_client.OpenClawAvailability
core.ura_openclaw_client.OpenClawClient
core.ura_openclaw_client.get_openclaw_client
dataclasses.dataclass
dataclasses.field
json
logging
os
shlex
typing.Any
```

# `scripts/pro/auditor_router.py`

- **Language:** python
- **Chunks:** 8

## Symbols

### function: `tailscale_status`
- Line: 42

def tailscale_status():
Obtiene estado de Tailscale en JSON.

### function: `detectar_relay`
- Line: 52

def detectar_relay(peer_name):
Detecta si alguna conexión usa relay (DERP).

Returns:
    {usa_relay: bool, conexiones_directas: int, conexiones_relay: int,
     peers: [{name, relay, direct_ip}]}

### function: `test_puerto`
- Line: 88

def test_puerto(host, puerto, protocolo, timeout):
Testea si un puerto está abierto.

### function: `test_velocidad_internet`
- Line: 108

def test_velocidad_internet():
Test rápido de velocidad de Internet.

### function: `auditoria_completa`
- Line: 125

def auditoria_completa(target):
Ejecuta auditoría completa del router y conectividad.

### function: `main`
- Line: 190

def main():

## Module Overview

Auditor de Router — Detecta relays, firewall, y sugiere puertos a abrir.

📖 MANUAL DE USO RÁPIDO:
  python3 scripts/pro/auditor_router.py              # Auditoría completa
  python3 scripts/pro/auditor_router.py --target hetzner-escudo  # Auditar conexión a Hetzner

🔒 OBJETIVO:
  - Detectar si la conexión ASUS→Hetzner pasa por relay (DERP) → limitada a 20 Mbps
  - Verificar NAT type, puertos UDP abiertos, capacidad real de subida
  - Si el router doméstico está estrangulando → sugerir puertos a abrir
  - Prohibir DERP relays: forzar conexión directa peer-to-peer

## Imports

```
argparse
json
os
pathlib.Path
socket
subprocess
time
```

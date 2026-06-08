# `core/resolver_red.py`

- **Language:** python
- **Chunks:** 8

## Symbols

### function: `cargar_inventario`
- Line: 35

def cargar_inventario():

### function: `resolver_dns`
- Line: 44

def resolver_dns(hostname):
Resuelve un hostname a IP usando DNS local + MagicDNS.

Prioridad:
  1. getent hosts (DNS local + /etc/hosts)
  2. tailscale status --json
  3. Inventario (config/dispositivos.json)

### function: `ping_latencia`
- Line: 87

def ping_latencia(ip, timeout):
Hace ping a una IP y devuelve (success, latencia_ms).

### function: `seleccionar_ruta`
- Line: 103

def seleccionar_ruta(hostname, inventario):
Selecciona la mejor ruta de conexión para un dispositivo.

Estrategia de conmutación:
  1. Intentar cable directo (<1ms óptimo)
  2. Si cable DOWN o latencia >5ms → Tailscale
  3. Si Tailscale DOWN → declarar OFFLINE

Returns:
    {ruta, ip, latencia_ms, metodo}

### function: `estado_red`
- Line: 147

def estado_red():
Escanea toda la red y devuelve estado de cada dispositivo.

### function: `main`
- Line: 183

def main():

## Module Overview

DNS Resolver + Network Failover — MagicDNS + Cable + Tailscale.

📖 MANUAL DE USO RÁPIDO:
  python3 core/resolver_red.py --resolver <hostname>    # Resolver DNS a IP
  python3 core/resolver_red.py --ping <hostname>        # Latencia cable vs Tailscale
  python3 core/resolver_red.py --status                 # Estado de toda la red

🔒 GARANTÍAS:
  - 0 IPs hardcodeadas. Todo por MagicDNS (gx10-64c3, mac-mini-de-ramon, etc.)
  - Prioridad: Cable físico (<1ms) → Tailscale (fallback)
  - Si latencia cable >5ms → conmuta a Tailscale automáticamente
  - Timeout 2s por ping, 3 intentos antes de declarar DOWN
  - Autenticación vía Tailscale SSH (sin passwords en texto plano)

Estrategia de resolución:
  1. Intentar resolver via getent hosts (DNS local + MagicDNS)
  2. Intentar via tailscale status --json (API local de Tailscale)
  3. Fallback: IPs del inventario (config/dispositivos.json)
  4. Conmutación: cable → Tailscale según latencia

## Imports

```
argparse
json
pathlib.Path
socket
subprocess
sys
time
```

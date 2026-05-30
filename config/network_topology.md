# Topología de Red URA — Canónica

**Última actualización:** 2026-05-11

## Triángulo principal (siempre vía Tailscale)

| Nodo | Tailscale IP | Rol | OS |
|---|---|---|---|
| Mac Mini | `100.123.81.101` | Orquestador / UI | macOS |
| GX10 (ASUS) | `10.164.1.99` | Inferencia LLM (Ollama) | Linux (Ubuntu) |
| ura-shield | `100.90.84.4` | Exit Node / VPN | Linux (Hetzner CX23 Nuremberg) |

## Puertos críticos

| Servicio | Host | Puerto | Acceso |
|---|---|---|---|
| Ollama API | GX10 | `11434` | `0.0.0.0` (toda red Tailscale) |
| SSH | GX10 | `22` | Solo Tailscale |
| Redis | Mac | `6379` | localhost |
| Postgres | Mac | `5432` | localhost |
| ura-panel | Mac | `8888` (nginx) | localhost |
| OpenClaw Gateway | Mac | `18789` | localhost |

## URLs operativas

- Ollama API: `http://10.164.1.99:11434`
- Configurado en: `~/URA/ura_ia_1972/.env` → `OLLAMA_HOST`

## IPs LAN (NO usar para automatización)

Inestables, pueden cambiar:
- Mac: `10.164.1.100` (Ethernet) / `10.164.1.17` (WiFi)
- GX10: `10.164.1.99` (Ethernet) / `10.164.1.247` (WiFi)

**Regla:** Para conexiones entre nodos siempre usar IP Tailscale (`100.x.x.x`).

## Exit Node Hetzner

- IP pública: `178.105.81.83`
- Activación: `tailscale up --exit-node=ura-shield --exit-node-allow-lan-access --accept-routes`
- Persistencia: `~/Library/LaunchAgents/com.ura.exitnode.plist`

## Credenciales (referencia, no almacenar aquí)

- `HCLOUD_TOKEN`: en `.bashrc`
- `TAILSCALE_AUTH_KEY`: en `.bashrc`
- SSH GX10: `321000` (PENDIENTE migrar a key-only)

# Conexión Hetzner — Topología y Fortalecimiento

## Topología de Red

```
               ┌───────────────┐
               │   HETZNER     │
               │ hetzner-escudo│
               │ 100.78.49.106 │
               │ 178.105.81.83 │
               └──────┬────────┘
                      │ Tailscale (directo, 51ms)
                      │ tx: 2.7GB / rx: 2.5GB
                      │
         ┌────────────┼────────────────────┐
         │            │                     │
         ▼            ▼                     ▼
┌─────────────────┐  │  ┌──────────────────┐
│ ASUS GX10       │  │  │ Mac Mini Ramón   │
│ gx10-64c3-1     │  │  │ mac-mini-de-ramon│
│ 100.72.103.12   │  │  │ 100.123.81.101   │
│                 │  │  │                  │
│ ETH: 10.164.1.99├──┘  │ ETH: 10.164.1.26 │
│ WIFI: 192.168.1 │     │                  │
│ .139            │     │ Tailscale:       │
└───────┬─────────┘     │ watchdog activo  │
        │               └──────────────────┘
        │ Cable Ethernet (métrica 100)
        │ 10.164.1.0/24
        ▼
┌─────────────────┐
│ Linksys Velop   │
│ 10.164.1.1      │
│ router/switch   │
└─────────────────┘
```

## Conexiones vs Servicios

| Conexión | Path | Latencia | Tipo | Failover |
|----------|------|----------|------|----------|
| ASUS → Hetzner | Tailscale directo | 51ms | VPN exit node | Solo Tailscale |
| ASUS → Mac | Ethernet 10.164.1.0/24 | <1ms | Cable | Tailscale (métrica 200) |
| Mac → Hetzner | Tailscale vía tailnet | 47ms | VPN | Solo Tailscale |
| Mac → ASUS | Ethernet 10.164.1.0/24 | <1ms | Cable | Tailscale (métrica 200) |
| ASUS → Internet | Hetzner exit node | 51ms | VPN exit node | Ethernet directa |

## Watchdogs y Auto-Recuperación

### En ASUS (GX10) — systemd + SNC + cron

| Componente | Frecuencia | Qué monitoriza | Acción al fallar |
|------------|-------------|----------------|------------------|
| **SNC** (snc.service) | Cada 10s | 9 servicios (ver runbook v2) | Reintenta reparar 2-3 veces, escala a OpenClaw |
| **ura-exit-node.sh** (cron) | Cada 60s | Internet vía Hetzner exit node | Re-conecta exit node, panic reset si sin internet |
| **ura-network.timer** | Cada 2min | Rutas de red, interfaces | Re-aplica métricas de failover |
| **network_failover.sh** | Cada 2min | Ethernet + Tailscale + WiFi | Re-configura rutas, repara Tailscale |
| **mac_heartbeat.py** | Cada 10s | Ping a Mac (Ethernet→Tailscale) | 3 fallos consecutivos → alerta, modo soberanía |
| **tailscale check** (SNC) | Cada 10s | Tailscale peers online | `systemctl restart tailscaled` + `tailscale up` |

### En Mac — launchd

| Componente | Frecuencia | Qué monitoriza | Acción al fallar |
|------------|-------------|----------------|------------------|
| **tailscale-watchdog** | Cada 30s | Peers online, peers críticos | `tailscale up --accept-routes`, notificación al usuario |
| **snc-remote** | Cada 10s | Estado SNC desde GX10 | Notificación si GX10 offline >30s |
| **ura_watcher** | Tiempo real (fswatch) | Cambios en repositorio | Sync a ASUS (debounce 10s) |

## Sistema de Failover Multi-Path

```
Orden de preferencia para ASUS → Mac:
  1. Ethernet enP7s7 (métrica 100)  ← primario
  2. Tailscale tailscale0 (métrica 200)  ← fallback
  3. WiFi wlP9s9 (métrica 300)  ← último recurso

Si Ethernet cae:
  - Kernel cambia automáticamente a Tailscale (métrica 200)
  - SNC detecta y repara Ethernet en <30s
  - ura-network.timer re-aplica rutas cada 2min

Si Tailscale cae en Mac:
  - tailscale-watchdog detecta en <30s
  - Reconoce automáticamente con `tailscale up`
  - Notifica al usuario si falla 3 veces seguidas
```

## Correcciones Aplicadas (2026-06-05)

### 1. SNC runbook v2
- **Añadido**: `tailscale` — check + repair del servicio Tailscale
- **Añadido**: `hetzner_connectivity` — ping a hetzner-escudo cada 10s
- **Añadido**: `wifi_failover` — monitoriza interfaz WiFi como fallback
- **Mejorado**: `network` — reparación con `&&` encadenado
- **Mejorado**: `mac_reachability` — multi-path: primero Ethernet, fallback Tailscale
- **Corregido**: `containers` — check ajustado a 3+ contenedores (no 5-9)

### 2. SNC engine fix
- **Corregido**: `run_command()` ahora detecta operadores shell (`|`, `&&`, `||`) y usa `shell=True` automáticamente
- **Antes**: checks con pipes fallaban siempre (grep no funcionaba en subprocess sin shell)

### 3. Mac Tailscale watchdog
- **Creado**: `deploy/ura_tailscale_watchdog.sh` — script que monitoriza peers cada 30s
- **Creado**: `deploy/com.ura.tailscale-watchdog.plist` — launchd para auto-arranque
- **Instalado**: corriendo como `com.ura.tailscale-watchdog` (PID activo)

### 4. ura-exit-node.sh
- **Corregido**: Log duplicado (cron redirigía stdout + script escribía al mismo archivo)
- **Corregido**: IP check cambiado de httpbin.org (caído) a ifconfig.me
- **Añadido**: Rotación de log a 500 líneas

### 5. network_failover.sh
- **Actualizado**: Interfaces reales detectadas (enP7s7, wlP9s9)
- **Añadido**: Verificación de Tailscale + Mac al final

### 6. error_logger.py
- **Corregido**: Bug `contextlib.suppress` → `suppress` (import incorrecto)
- **SNC se caía al arrancar por este error** — ahora arranca correctamente

#!/bin/bash
set -euo pipefail

echo "Aplica con: sudo bash scripts/pro/ufw_apply.sh"

if [ "$EUID" -ne 0 ]; then
    echo "ERROR: Ejecutar como root (sudo)." >&2
    exit 1
fi

ufw --force reset

# SSH
ufw allow ssh

# Servicios URA (solo LAN)
ufw allow from 10.164.1.0/24 to any port 8000 proto tcp  # ura-api
ufw allow from 10.164.1.0/24 to any port 8080 proto tcp  # ura-audit-api
ufw allow from 10.164.1.0/24 to any port 8002 proto tcp  # ura-contraste
ufw allow from 10.164.1.0/24 to any port 8888 proto tcp  # ura-metrics

# Model Router (solo LAN)
ufw allow from 10.164.1.0/24 to any port 11434 proto tcp  # ollama
ufw allow from 10.164.1.0/24 to any port 11435 proto tcp  # model-router

# OpenClaw (solo LAN)
ufw allow from 10.164.1.0/24 to any port 18789 proto tcp

# Cámaras (solo VLAN específica)
ufw allow from 192.168.0.0/16 to any port 1984 proto tcp  # go2rtc
ufw allow from 192.168.0.0/16 to any port 554 proto tcp    # RTSP

# Prometheus scrape desde Docker
ufw allow from 172.17.0.0/16 to any port 8002 proto tcp

# Tailscale (todo el tráfico)
ufw allow in on tailscale0

# Open WebUI (solo LAN)
ufw allow from 10.164.1.0/24 to any port 3080 proto tcp

# Denegar resto
ufw default deny incoming
ufw default allow outgoing

ufw --force enable
ufw status verbose

#!/usr/bin/env bash
# heartbeat_hetzner.sh — Verify Hetzner connectivity, restart Tailscale if down.
# Called by cron every 5 minutes.
set -euo pipefail

HETZNER_MAGICDNS="${HETZNER_MAGICDNS:-hetzner-node.tail-net.ts.net}"
HETZNER_PORT="${HETZNER_PORT:-8081}"
LOG="/dev/null"

# Only run if the endpoint resolves (Hetzner may be offline indefinitely)
if ! host "$HETZNER_MAGICDNS" >/dev/null 2>&1; then
    exit 0
fi

if ! nc -zw3 "$HETZNER_MAGICDNS" "$HETZNER_PORT" 2>/dev/null; then
    logger -t heartbeat-hetzner "Hetzner unreachable via $HETZNER_MAGICDNS:$HETZNER_PORT — restarting Tailscale"
    sudo tailscale-up --reset 2>&1 | logger -t heartbeat-hetzner
fi

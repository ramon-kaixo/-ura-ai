#!/bin/bash
set -euo pipefail
# watchdog_tailscale.sh - Monitoriza y reconecta automaticamente Tailscale
CHECK_INTERVAL=30
GX10_URL="http://10.164.1.99:11434/api/tags"
MAX_RETRIES=3

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [tailscale-watchdog] $1"
}

check_tailscale() {
    tailscale status >/dev/null 2>&1 && curl -s --max-time 5 "$GX10_URL" >/dev/null 2>&1
}

reconnect_tailscale() {
    local retries=0
    while [ $retries -lt $MAX_RETRIES ]; do
        log "Intentando reconectar Tailscale (intento $retries/$MAX_RETRIES)..."
        tailscale up --accept-routes 2>/dev/null && sleep 5
        if check_tailscale; then
            log "✅ Tailscale reconectado"
            return 0
        fi
        retries=$((retries + 1))
        sleep 10
    done
    log "❌ No se pudo reconectar Tailscale tras $MAX_RETRIES intentos"
    return 1
}

log "Iniciando watchdog de Tailscale"

while true; do
    if ! check_tailscale; then
        log "🔴 Tailscale desconectado. Intentando reconectar..."
        reconnect_tailscale || true
    fi
    sleep $CHECK_INTERVAL
done

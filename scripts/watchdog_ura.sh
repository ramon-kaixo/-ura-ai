#!/bin/bash
set -euo pipefail
# watchdog_ura.sh - Watchdog principal de URA: Bluetooth, Tailscale, AgenteVoz
REPO="$(cd "$(dirname "$0")/.." && pwd)"
LOG_FILE="/tmp/ura_watchdog.log"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [ura-watchdog] $1" | tee -a "$LOG_FILE"
}

check_bluetooth_input() {
    system_profiler SPAudioDataType 2>/dev/null | grep -q "Transport: Bluetooth"
}

check_tailscale() {
    tailscale status >/dev/null 2>&1
}

check_agente_voz() {
    pgrep -f "agente_voz.*bucle" >/dev/null 2>&1
}

start_agente_voz() {
    if check_agente_voz; then
        return 0
    fi
    log "Iniciando AgenteVoz..."
    cd "$REPO" && PYTHONPATH="$REPO" .venv/bin/python3 -c "
import sys; sys.path.insert(0, '$REPO')
from agents.agente_voz import AgenteVoz
import logging; logging.basicConfig(level=logging.INFO)
agente = AgenteVoz(); agente.bucle()
" &>/tmp/ura_agente_voz.log &
    sleep 5
    if check_agente_voz; then
        log "✅ AgenteVoz iniciado (PID $(pgrep -f 'agente_voz.*bucle'))"
    else
        log "❌ Fallo al iniciar AgenteVoz"
    fi
}

reconnect_bluetooth() {
    HEADSET_MAC="F4:4E:FD:84:97:83"
    log "Reconectando Bluetooth..."
    blueutil --connect "$HEADSET_MAC" 2>/dev/null && sleep 3
    if check_bluetooth_input; then
        log "✅ Bluetooth reconectado"
    else
        log "⚠️ Bluetooth no reconectado"
    fi
}

reconnect_tailscale() {
    log "Reconectando Tailscale..."
    tailscale up --accept-routes 2>/dev/null && sleep 5
    if check_tailscale; then
        log "✅ Tailscale reconectado"
    else
        log "⚠️ Tailscale no reconectado"
    fi
}

log "Watchdog URA iniciado"

while true; do
    # Verificar Bluetooth
    if ! check_bluetooth_input; then
        log "🔴 Microfono Bluetooth no detectado"
        reconnect_bluetooth
    fi

    # Verificar Tailscale
    if ! check_tailscale; then
        log "🔴 Tailscale desconectado"
        reconnect_tailscale
    fi

    # Verificar AgenteVoz
    start_agente_voz

    sleep 30
done

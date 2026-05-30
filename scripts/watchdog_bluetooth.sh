#!/bin/bash
set -euo pipefail
# watchdog_bluetooth.sh - Monitoriza y reconecta automaticamente el microfono Bluetooth
HEADSET_MAC="${HEADSET_MAC:-F4:4E:FD:84:97:83}"
HEADSET_NAME="${HEADSET_NAME:-Vieta Pro Easy 2}"
CHECK_INTERVAL=30
MAX_RETRIES=3

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [bluetooth-watchdog] $1"
}

check_bluetooth_input() {
    system_profiler SPAudioDataType 2>/dev/null | grep -q "Transport: Bluetooth"
}

connect_headset() {
    local retries=0
    while [ $retries -lt $MAX_RETRIES ]; do
        if blueutil --connect "$HEADSET_MAC" 2>/dev/null; then
            sleep 3
            if check_bluetooth_input; then
                log "✅ $HEADSET_NAME conectado como entrada de audio"
                return 0
            fi
        fi
        retries=$((retries + 1))
        log "⚠️ Intento $retries/$MAX_RETRIES fallido. Reintentando..."
        sleep 5
    done
    log "❌ No se pudo conectar $HEADSET_NAME tras $MAX_RETRIES intentos"
    return 1
}

log "Iniciando watchdog de Bluetooth para $HEADSET_NAME ($HEADSET_MAC)"

while true; do
    if ! check_bluetooth_input; then
        log "🔴 Microfono Bluetooth no detectado. Intentando reconectar..."
        connect_headset || true
    fi
    sleep $CHECK_INTERVAL
done

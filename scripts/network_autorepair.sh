#!/bin/bash
# network_autorepair.sh - Autocuración de red para URA/Laia (macOS/Linux)
# Se ejecuta en segundo plano desde el bucle autónomo cada 10 min.

set -euo pipefail

MAX_FAILS=5
FAIL_COUNT_FILE="/tmp/network_fail_count"
LOG_FILE="/tmp/autonomia_network.log"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOG_FILE"
}

if [[ "$OSTYPE" == "darwin"* ]]; then
    GATEWAY_IP="8.8.8.8"
    INTERFACE_NAME=$(networksetup -listallhardwareports | awk '/Hardware Port: Wi-Fi/{getline; print $NF}' | head -1)
    PING_CMD="ping -c 2 -t 5"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    GATEWAY_IP="8.8.8.8"
    INTERFACE_NAME=$(ip route | grep default | awk '{print $5}' | head -1)
    PING_CMD="ping -c 2 -W 5"
else
    log "SO no soportado: $OSTYPE"
    exit 0
fi

do_ping() {
    $PING_CMD "$GATEWAY_IP" > /dev/null 2>&1
}

if [ ! -f "$FAIL_COUNT_FILE" ]; then
    echo "0" > "$FAIL_COUNT_FILE"
fi
FAIL_COUNT=$(cat "$FAIL_COUNT_FILE")

if do_ping; then
    echo "0" > "$FAIL_COUNT_FILE"
    log "Red OK, contador reset."
    exit 0
fi

FAIL_COUNT=$((FAIL_COUNT+1))
echo "$FAIL_COUNT" > "$FAIL_COUNT_FILE"
log "Fallo $FAIL_COUNT de $MAX_FAILS"

if [ "$FAIL_COUNT" -ge "$MAX_FAILS" ]; then
    log "Aplicando medidas de autocuracion..."
    URA_BASE="$(cd "$(dirname "$0")/.." && pwd)"
    NOTIFICAR="$URA_BASE/scripts/notificar.sh"
    if [[ -x "$NOTIFICAR" ]]; then
        "$NOTIFICAR" "ALERTA: Caida de red persistente. Aplicando protocolo."
    fi

    if [[ "$OSTYPE" == "darwin"* ]]; then
        networksetup -setairportpower "$INTERFACE_NAME" off 2>/dev/null || true
        sleep 5
        networksetup -setairportpower "$INTERFACE_NAME" on 2>/dev/null || true
        sleep 5
        if do_ping; then
            log "Recuperado tras reinicio Wi-Fi."
            exit 0
        fi
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Reiniciar interfaz
        sudo ip link set "$INTERFACE_NAME" down 2>/dev/null || true
        sleep 2
        sudo ip link set "$INTERFACE_NAME" up 2>/dev/null || true
        sleep 5
        if do_ping; then
            log "Recuperado tras reinicio de interfaz."
            exit 0
        fi
        # Reiniciar servicios de red
        if systemctl is-active --quiet systemd-networkd 2>/dev/null; then
            sudo systemctl restart systemd-networkd 2>/dev/null || true
        elif systemctl is-active --quiet NetworkManager 2>/dev/null; then
            sudo systemctl restart NetworkManager 2>/dev/null || true
        fi
        sleep 10
        if do_ping; then
            log "Recuperado tras reinicio de servicios."
            exit 0
        fi
        # Intentar módem 4G
        MODEM_SCRIPT="$URA_BASE/scripts/modem_4g_autoconnect.sh"
        if [[ -x "$MODEM_SCRIPT" ]]; then
            "$MODEM_SCRIPT"
            sleep 10
            if do_ping; then
                log "Recuperado via modem 4G."
                exit 0
            fi
        fi
    fi
    # Ultimo recurso: reiniciar
    log "Recuperacion fallida. Reiniciando sistema..."
    if [[ -x "$NOTIFICAR" ]]; then
        "$NOTIFICAR" "CRITICO: Reiniciando equipo por caida de red."
    fi
    sudo reboot
fi

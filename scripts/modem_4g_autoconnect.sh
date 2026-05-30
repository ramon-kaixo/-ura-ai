#!/bin/bash
# modem_4g_autoconnect.sh - Levantar módem 4G si falla la red principal
# Dependencias: usb-modeswitch, wvdial, ppp

LOG_FILE="/tmp/ura_modem_4g.log"

# Solo actuar si no hay conectividad (ni siquiera ping a gateway)
if ping -c 2 8.8.8.8 > /dev/null 2>&1; then
    exit 0
fi

# Ya hay interfaz ppp0?
if ifconfig 2>/dev/null | grep -q "ppp0" || ip addr 2>/dev/null | grep -q "ppp0"; then
    echo "$(date): Modem 4G ya conectado (ppp0 activo)." >> "$LOG_FILE"
    exit 0
fi

echo "$(date): Red principal caida. Intentando conectar modem 4G..." >> "$LOG_FILE"

# Opcional: cambiar modo del módem (ejemplo con Huawei)
if command -v usb_modeswitch >/dev/null 2>&1; then
    usb_modeswitch -v 0x12d1 -p 0x1f01 -M "55534243123456780000000000000a" 2>/dev/null || true
    sleep 3
fi

# Levantar conexión con wvdial
if command -v pon >/dev/null 2>&1; then
    pon wvdial 2>> "$LOG_FILE"
    sleep 5
    if ifconfig 2>/dev/null | grep -q "ppp0" || ip addr 2>/dev/null | grep -q "ppp0"; then
        echo "$(date): Modem 4G conectado exitosamente." >> "$LOG_FILE"
        URA_BASE="$(cd "$(dirname "$0")/.." && pwd)"
        NOTIFICAR="$URA_BASE/scripts/notificar.sh"
        if [[ -x "$NOTIFICAR" ]]; then
            "$NOTIFICAR" "INFO: Conectividad restaurada mediante modem 4G de respaldo."
        fi
        exit 0
    else
        echo "$(date): Fallo al conectar modem 4G." >> "$LOG_FILE"
        URA_BASE="$(cd "$(dirname "$0")/.." && pwd)"
        NOTIFICAR="$URA_BASE/scripts/notificar.sh"
        if [[ -x "$NOTIFICAR" ]]; then
            "$NOTIFICAR" "ALERTA: No se pudo establecer conexion 4G de respaldo."
        fi
        exit 1
    fi
else
    echo "$(date): wvdial no instalado. No se puede activar 4G." >> "$LOG_FILE"
    exit 1
fi

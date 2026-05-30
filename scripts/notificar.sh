#!/bin/bash
set -euo pipefail
# notificar.sh — Sistema unificado de notificaciones
# Uso: notificar.sh "mensaje" [info|warn|error] [telegram|mac|log|all]

MENSAJE="$1"; NIVEL="${2:-info}"; CANAL="${3:-all}"
LOG="/tmp/ura_notificaciones.log"

notificar_telegram() {
    [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_CHAT_ID:-}" ] && \
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${TELEGRAM_CHAT_ID}" -d "text=[${NIVEL^^}] $MENSAJE" >/dev/null 2>&1 || true
}
notificar_mac() {
    osascript -e "display notification \"$MENSAJE\" with title \"URA ${NIVEL^^}\"" 2>/dev/null || true
}
notificar_log() {
    echo "[$(date)] [${NIVEL^^}] $MENSAJE" >> "$LOG"
}

case "$CANAL" in
    telegram) notificar_telegram ;;
    mac)      notificar_mac ;;
    log)      notificar_log ;;
    all)      notificar_telegram; notificar_mac; notificar_log ;;
esac

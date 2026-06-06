#!/bin/bash
# Health Check Automático para Model Router
# Ejecutar cada 5 minutos via cron o systemd timer

ROUTER_URL="http://127.0.0.1:11435/health"
LOG_FILE="/var/log/ura_router_health.log"
ALERT_THRESHOLD=3  # Número de fallos consecutivos antes de alertar
STATE_FILE="/tmp/ura_router_health.state"

mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# Leer estado anterior
if [ -f "$STATE_FILE" ]; then
    FAIL_COUNT=$(cat "$STATE_FILE")
else
    FAIL_COUNT=0
fi

# Verificar health endpoint
if curl -s -f "$ROUTER_URL" > /dev/null 2>&1; then
    if [ "$FAIL_COUNT" -gt 0 ]; then
        log "✅ Router recuperado después de $FAIL_COUNT fallos"
        FAIL_COUNT=0
        echo "$FAIL_COUNT" > "$STATE_FILE"
    fi
    log "✅ Health check OK"
    exit 0
else
    FAIL_COUNT=$((FAIL_COUNT + 1))
    echo "$FAIL_COUNT" > "$STATE_FILE"
    log "❌ Health check FAILED (fallos consecutivos: $FAIL_COUNT/$ALERT_THRESHOLD)"
    
    if [ "$FAIL_COUNT" -ge "$ALERT_THRESHOLD" ]; then
        log "🚨 ALERTA: Router no responde después de $FAIL_COUNT fallos consecutivos"
        # Reiniciar servicio
        systemctl restart model-router.service
        log "🔄 Servicio reiniciado"
    fi
    exit 1
fi

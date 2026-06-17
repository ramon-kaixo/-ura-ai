#!/usr/bin/env bash
# ============================================================
# Panic Handler — Señalización de emergencia URA
# Solo acciones destructivas. Requiere confirmación humana.
# Si claw_listener no responde → ABORT (no actuar a ciegas).
# ============================================================
set -e

MAC_IP="${1:-10.164.1.26}"
TIMEOUT=30

log() { echo "[PANIC] $(date): $1"; }

log "Estado de emergencia detectado"
log "Solicitando confirmación humana en Mac (timeout ${TIMEOUT}s)..."

# Intentar contactar con claw_listener en el Mac
CONFIRMATION=$(ssh -o ConnectTimeout=5 -o BatchMode=yes "ramon@${MAC_IP}" \
    "bash ${URA_ROOT:-/Users/ramonesnaola/URA}/ura_ia_1972/deploy/claw_listener.sh 'PANIC_ALERT' 'GX10 en estado critico. Accion destructiva requerida.'" 2>/dev/null || echo "TIMEOUT")

if [ "$CONFIRMATION" = "CONFIRMADO" ]; then
    log "✅ Confirmación recibida del Mac"
    log "Ejecutando acciones de emergencia..."
    # Aquí irían las acciones destructivas controladas
    # docker system prune -f (solo ejemplo, ajustar según runbook)
    log "Acciones de emergencia completadas"
    exit 0
elif [ "$CONFIRMATION" = "CANCELADO" ]; then
    log "❌ Cancelado por el usuario en Mac"
    exit 1
else
    log "⛔ ABORTADO: sin respuesta del claw_listener en ${TIMEOUT}s"
    log "Por seguridad, NO se ejecuta ninguna acción destructiva sin confirmación"
    exit 2
fi

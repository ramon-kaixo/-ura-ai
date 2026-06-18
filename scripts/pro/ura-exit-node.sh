#!/bin/bash
LOG="/home/ramon/ura-exit-node.log"
EXIT_NODE="hetzner-escudo"
TAILSCALE="sudo tailscale"

log() {
    local msg="[$(date "+%Y-%m-%d %H:%M:%S")] $1"
    echo "$msg" >> "$LOG"
}

rotate_log() {
    local max_lines=${URA_LOG_MAX_LINES:-500}
    if [ -f "$LOG" ] && [ "$(wc -l < "$LOG")" -gt "$max_lines" ]; then
        tail -n "$max_lines" "$LOG" > "${LOG}.tmp" && mv "${LOG}.tmp" "$LOG"
    fi
}

panic_reset() {
    log "PANICO: Sin internet - desconectando exit node"
    $TAILSCALE up --exit-node=
    sleep 3
    if curl -s --max-time 5 https://google.com -o /dev/null; then
        log "OK: Internet restaurado (sin exit node)"
    else
        log "FALLO: Sin internet incluso sin exit node"
    fi
}

safe_up() {
    log "Conectando exit node -> $EXIT_NODE"
    $TAILSCALE up --exit-node="$EXIT_NODE" --exit-node-allow-lan-access --accept-routes
    sleep 5
    if curl -s --max-time 5 https://google.com -o /dev/null; then
        log "OK: Exit node activo (via $EXIT_NODE)"
        return 0
    else
        log "FALLO: Exit node sin internet - reseteando"
        panic_reset
        return 1
    fi
}

# === MAIN ===
rotate_log
log "=== ura-exit-node.sh ==="

# 1. Panic button: if no internet, reset immediately
if ! curl -s --max-time 5 https://google.com -o /dev/null; then
    log "AVISO: Sin internet detectado"
    panic_reset
    exit 1
fi

# 2. Check if already on exit node
CURRENT_IP=$(curl -s --max-time 5 https://ifconfig.me 2>/dev/null || echo "")
if echo "$CURRENT_IP" | grep -q "^178.105.81"; then
    log "OK: Ya en Hetzner ($CURRENT_IP)"
    exit 0
fi

# 3. Connect exit node
safe_up

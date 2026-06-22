#!/bin/bash
# ============================================================
# opencode_health.sh — Health check conexión Mac ↔ ASUS
# Verifica: OpenCode local, SSH, Model Router, ura-executor,
# SingletonSocket, RAM/CPU.
#
# Uso: bash deploy/opencode_health.sh        # Salida legible
#      bash deploy/opencode_health.sh --json  # Salida JSON
# ============================================================
set -u
MODE="${1:-text}"
ASUS_IP="${ASUS_HOST:-10.164.1.99}"
ASUS_USER="ramon"
LOG_FILE="${HOME}/URA/logs/opencode_health.log"
SUPPORT_DIR="${HOME}/Library/Application Support/ai.opencode.desktop"
MAX_RAM_MB=2000

mkdir -p "$(dirname "$LOG_FILE")"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"; }

check() {
    local label="$1" status="$2" detail="$3"
    if [ "$MODE" = "--json" ]; then
        json_checks="${json_checks}{\"check\":\"$label\",\"status\":\"$status\",\"detail\":\"$detail\"},"
    else
        local icon="✅"
        [ "$status" != "ok" ] && icon="❌"
        printf "  %s %-30s %s\n" "$icon" "$label" "$detail"
    fi
}

# === MAIN ===
errors=0
json_checks=""

if [ "$MODE" = "--json" ]; then
    echo "{"
    echo "  \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\","
    echo "  \"checks\": ["
else
    echo ""
    echo "╔══════════════════════════════════════════════════════╗"
    echo "║     OpenCode Health Check — Mac ↔ GX10              ║"
    echo "╚══════════════════════════════════════════════════════╝"
    echo ""
fi

# ── 1. OpenCode local ────────────────────────────────────────
PID=$(pgrep -f '/Applications/OpenCode.app/Contents/MacOS/OpenCode$' 2>/dev/null || echo "")
if [ -n "$PID" ]; then
    RAM=$(ps -o rss= -p "$PID" 2>/dev/null | awk '{printf "%.0f", $1/1024}' || echo 0)
    CPU=$(ps -o %cpu= -p "$PID" 2>/dev/null | awk '{printf "%.1f", $1}' || echo 0)
    detail="PID ${PID}, ${RAM}MB RAM, ${CPU}% CPU"
    [ "$RAM" -gt "$MAX_RAM_MB" ] && detail="${detail} ⚠ >${MAX_RAM_MB}MB"
    check "OpenCode Main" "ok" "$detail"
else
    check "OpenCode Main" "fail" "No running"
    errors=$((errors + 1))
fi

# ── 2. Helpers zombies ──────────────────────────────────────
HELPERS=$(pgrep -f 'OpenCode Helper' 2>/dev/null | wc -l | tr -d ' ' || echo 0)
MAIN_UP=$(pgrep -f '/Applications/OpenCode.app/Contents/MacOS/OpenCode$' 2>/dev/null | wc -l | tr -d ' ' || echo 0)
if [ "$MAIN_UP" -eq 0 ] && [ "$HELPERS" -gt 0 ]; then
    check "Zombie helpers" "fail" "${HELPERS} helper(s) sin Main"
    errors=$((errors + 1))
elif [ "$HELPERS" -gt 0 ]; then
    check "Helpers" "ok" "${HELPERS} helper(s) activos"
else
    check "Helpers" "ok" "ninguno (OpenCode no corriendo)"
fi

# ── 3. SingletonSocket ─────────────────────────────────────
SOCK="${SUPPORT_DIR}/SingletonSocket"
if [ -L "$SOCK" ]; then
    TARGET=$(readlink "$SOCK" 2>/dev/null || echo "")
    if [ -n "$TARGET" ] && [ -e "$TARGET" ]; then
        check "SingletonSocket" "ok" "→ ${TARGET}"
    else
        check "SingletonSocket" "fail" "Huérfano: → ${TARGET:-missing}"
        errors=$((errors + 1))
    fi
else
    check "SingletonSocket" "warn" "No existe (OpenCode no corriendo)"
fi

# ── 4. Ping ASUS ────────────────────────────────────────────
if ping -c 1 -W 2 "$ASUS_IP" >/dev/null 2>&1; then
    check "Ping GX10" "ok" "${ASUS_IP} reachable"
else
    check "Ping GX10" "fail" "${ASUS_IP} unreachable"
    errors=$((errors + 1))
fi

# ── 5. SSH ASUS ─────────────────────────────────────────────
SSH_RESULT=$(ssh -o ConnectTimeout=5 -o BatchMode=yes "$ASUS_USER@$ASUS_IP" "echo ok" 2>/dev/null || true)
if echo "$SSH_RESULT" | grep -q ok; then
    check "SSH GX10" "ok" "${ASUS_USER}@${ASUS_IP}"
else
    check "SSH GX10" "fail" "No se pudo conectar SSH"
    errors=$((errors + 1))
fi

# ── 6. Model Router ─────────────────────────────────────────
if curl -sf --max-time 3 "http://${ASUS_IP}:11435/health" >/dev/null 2>&1; then
    check "Model Router" "ok" "port 11435"
else
    check "Model Router" "fail" "port 11435 no responde"
    errors=$((errors + 1))
fi

# ── 7. OpenCode server en ASUS ──────────────────────────────
OC_STATUS=$(ssh -o ConnectTimeout=5 "$ASUS_USER@$ASUS_IP" "systemctl is-active opencode.service" 2>/dev/null || true)
OC_STATUS="${OC_STATUS:-unknown}"
if [ "$OC_STATUS" = "active" ]; then
    check "OpenCode GX10" "ok" "service active"
else
    check "OpenCode GX10" "fail" "service: ${OC_STATUS}"
    errors=$((errors + 1))
fi

# ── 8. ura-executor ─────────────────────────────────────────
UX_STATUS=$(ssh -o ConnectTimeout=5 "$ASUS_USER@$ASUS_IP" "systemctl is-active ura-executor.service" 2>/dev/null || true)
UX_STATUS="${UX_STATUS:-unknown}"
if [ "$UX_STATUS" = "active" ]; then
    check "ura-executor" "ok" "port 4096 active"
else
    check "ura-executor" "fail" "service: ${UX_STATUS}"
    errors=$((errors + 1))
fi

# ── 9. Config en Mac ───────────────────────────────────────
if [ -f "${HOME}/.config/opencode/opencode.jsonc" ]; then
    SIZE=$(wc -c < "${HOME}/.config/opencode/opencode.jsonc" | tr -d ' ')
    [ "$SIZE" -gt 100 ] && detail="OK (${SIZE}B)" || detail="Esqueleto (${SIZE}B)"
    check "opencode.jsonc" "ok" "$detail"
else
    check "opencode.jsonc" "fail" "No existe"
    errors=$((errors + 1))
fi

# ── 10. Espacio en disco OpenCode ──────────────────────────
APP_SIZE=$(du -sh /Applications/OpenCode.app 2>/dev/null | awk '{print $1}' || true)
APP_SIZE="${APP_SIZE:-0}"
DATA_SIZE=$(du -sh "${SUPPORT_DIR}" 2>/dev/null | awk '{print $1}' || true)
DATA_SIZE="${DATA_SIZE:-0}"
CACHE_SIZE=$(du -sh "${HOME}/Library/Caches/@opencode-aidesktop-updater" 2>/dev/null | awk '{print $1}' || true)
CACHE_SIZE="${CACHE_SIZE:-0}"
check "Disco" "ok" "App ${APP_SIZE}, Datos ${DATA_SIZE}, Cache ${CACHE_SIZE}"

# === RESULT ===
if [ "$MODE" = "--json" ]; then
    json_checks="${json_checks%?}"  # remove trailing comma
    echo "  ${json_checks}]"
    echo "  ,\"errors\": $errors"
    echo "}"
else
    echo ""
    if [ "$errors" -eq 0 ]; then
        echo "  ✅ RESULTADO: TODO OK (0 errores)"
    else
        echo "  ❌ RESULTADO: ${errors} error(es) detectados"
    fi
    echo ""
fi

exit "$errors"

#!/bin/bash
set -euo pipefail
# ura_watchdog.sh — Monitoriza servicios y notifica fallos
ERROR_LOG="/tmp/ura_errors.log"
SEARXNG_URL="${SEARXNG_URL:-http://178.105.81.83:8888}"
GX10_URL="http://10.164.1.99:11434/api/tags"
FRIGATE_URL="${FRIGATE_URL:-http://10.164.1.99:5000}"
UMBRAL_FALLOS=3

for servicio in "SearXNG" "GX10" "Frigate"; do
    if [ "$servicio" = "SearXNG" ]; then
        if curl -s --max-time 5 "${SEARXNG_URL}/search?q=test&format=json" >/dev/null 2>&1; then
            sed -i '' "/SearXNG no responde/d" "$ERROR_LOG" 2>/dev/null || true
        else
            echo "$(date) SearXNG no responde" >> "$ERROR_LOG"
        fi
        FALLOS=$(grep -c "SearXNG no responde" "$ERROR_LOG" 2>/dev/null || echo 0)
    elif [ "$servicio" = "GX10" ]; then
        if curl -s --max-time 5 "$GX10_URL" >/dev/null 2>&1; then
            sed -i '' "/GX10 no responde/d" "$ERROR_LOG" 2>/dev/null || true
        else
            echo "$(date) GX10 no responde" >> "$ERROR_LOG"
        fi
        FALLOS=$(grep -c "GX10 no responde" "$ERROR_LOG" 2>/dev/null || echo 0)
    else
        if curl -s --max-time 5 "${FRIGATE_URL}/api/stats" >/dev/null 2>&1; then
            sed -i '' "/Frigate no responde/d" "$ERROR_LOG" 2>/dev/null || true
        else
            echo "$(date) Frigate no responde" >> "$ERROR_LOG"
        fi
        FALLOS=$(grep -c "Frigate no responde" "$ERROR_LOG" 2>/dev/null || echo 0)
    fi

    if [ "$FALLOS" -ge "$UMBRAL_FALLOS" ]; then
        MSG="⚠️ $servicio no responde ($FALLOS fallos consecutivos)"
        if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_CHAT_ID:-}" ]; then
            curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
                -d "chat_id=${TELEGRAM_CHAT_ID}" -d "text=$MSG" >/dev/null 2>&1 || true
        fi
        osascript -e "display notification \"$MSG\" with title \"URA Alert\"" 2>/dev/null || true
        echo "$MSG"
    fi
done

# Monitorizar espacio en disco
DISCO=$(df -h / 2>/dev/null | tail -1 | awk '{print $5}' | sed 's/%//' || echo 0)
if [ "$DISCO" -gt 80 ]; then
    MSG="⚠️ Disco al ${DISCO}%. Revisa /tmp/"
    if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_CHAT_ID:-}" ]; then
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d "chat_id=${TELEGRAM_CHAT_ID}" -d "text=$MSG" >/dev/null 2>&1 || true
    fi
    osascript -e "display notification \"$MSG\" with title \"URA Alert\"" 2>/dev/null || true
    echo "$MSG"
fi

# Verificar montaje del volumen SMB (Desactivado montaje automático para evitar ventanas de error)
# if ! mount | grep -q "/Volumes/Compartida"; then
#     echo "$(date) SMB no montado" >> "$ERROR_LOG"
#     bash "${REPO}/scripts/mount_smb.sh" &
# fi

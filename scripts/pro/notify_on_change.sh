#!/bin/bash
# notify_on_change.sh – Envia resumen de cambios Git recientes por notificacion
# Uso: notify_on_change.sh [--since 24h]
set -e

SINCE="${2:-24h}"
REPO="/Users/ramonesnaola/URA/ura_ia_1972"
LOG="/var/log/ura_notify_change.log"

echo "$(date) - Notificando cambios de las ultimas $SINCE..." >> "$LOG"

cd "$REPO"

CHANGES=$(git log --oneline --since="$SINCE" --format="%h %s (%ar)" 2>/dev/null)

if [ -z "$CHANGES" ]; then
    echo "Sin cambios en las ultimas $SINCE" >> "$LOG"
    exit 0
fi

COUNT=$(echo "$CHANGES" | wc -l | tr -d ' ')
SUMMARY=$(echo "$CHANGES" | head -10)

MESSAGE="Cambios en URA (ultimas ${SINCE}): ${COUNT} commits"
DETAIL=$(echo "$SUMMARY" | tr '\n' ';' | cut -c1-500)

if [ -x /opt/ura/scripts/notificar.sh ]; then
    /opt/ura/scripts/notificar.sh "$MESSAGE" 2>/dev/null || true
fi

echo "$MESSAGE" >> "$LOG"
echo "$DETAIL" >> "$LOG"
echo "" >> "$LOG"

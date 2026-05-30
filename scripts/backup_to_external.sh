#!/bin/bash
set -euo pipefail
SOURCE="${HOME}/URA/ura_ia_1972"
DEST_HOST="10.164.1.18"
DEST_FALLBACK="10.164.1.99"
DEST_PATH="/backup/URA"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOGFILE="${HOME}/logs/backup.log"
mkdir -p "$(dirname "$LOGFILE")"
if ping -c 1 -W 2 "$DEST_HOST" &>/dev/null; then
    echo "[$(date)] Thunderbolt activo. Backup rápido." >> "$LOGFILE"
    rsync -avz --delete "$SOURCE/" "${DEST_HOST}:${DEST_PATH}/" >> "$LOGFILE" 2>&1
elif ping -c 1 -W 2 "$DEST_FALLBACK" &>/dev/null; then
    echo "[$(date)] Thunderbolt no disponible. Usando Tailscale." >> "$LOGFILE"
    rsync -avz --delete "$SOURCE/" "${DEST_FALLBACK}:${DEST_PATH}/" >> "$LOGFILE" 2>&1
else
    echo "[$(date)] 🔴 Sin conectividad con el destino de backup." >> "$LOGFILE"
    exit 1
fi
echo "[$(date)] ✅ Backup completado." >> "$LOGFILE"

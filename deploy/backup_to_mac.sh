#!/bin/bash
# ============================================================
# backup_to_mac.sh — Backup GX10 → Mac
# Ejecutado por cron en GX10: 0 3 * * *
# ============================================================
set -euo pipefail

MAC_USER="ramonesnaola"
MAC_IP="10.164.1.26"
BACKUP_DIR="/Users/ramonesnaola/URA/backups_gx10"
SOURCE_DIR="/home/ramon/URA"
LOG_FILE="/home/ramon/URA/logs/backup_to_mac.log"
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
BWLIMIT=${URA_BWLIMIT:-10000}  # 10 MB/s default

mkdir -p "$(dirname "$LOG_FILE")"

log() { echo "[$(date)] $*" >> "$LOG_FILE"; echo "$*"; }

log "=== Backup ${TIMESTAMP} ==="

# 1. Verificar conectividad
if ! ping -c 1 -W 3 "$MAC_IP" >/dev/null 2>&1; then
    log "ERROR: Mac ($MAC_IP) no alcanzable"
    exit 1
fi

# 2. Backup rsync con bwlimit
log "Iniciando rsync (bwlimit=${BWLIMIT}KB/s)..."
rsync -avz --delete \
    --bwlimit="$BWLIMIT" \
    --exclude="*.pyc" \
    --exclude="__pycache__" \
    --exclude=".git" \
    --exclude="node_modules" \
    --exclude="*.log" \
    --exclude=".venv" \
    --exclude="quarantine" \
    "$SOURCE_DIR/" "${MAC_USER}@${MAC_IP}:${BACKUP_DIR}/" >> "$LOG_FILE" 2>&1

if [ $? -eq 0 ]; then
    log "Backup completado"
    # Rotar logs viejos (>7 días)
    find "$(dirname "$LOG_FILE")" -name "backup_to_mac.log*" -mtime +7 -delete 2>/dev/null || true
    exit 0
else
    log "ERROR: rsync falló"
    exit 1
fi

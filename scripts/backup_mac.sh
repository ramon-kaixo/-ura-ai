#!/bin/bash
# backup_mac.sh — Backup URA → Mac por SSH
# Uso: bash scripts/backup_mac.sh
set -euo pipefail

MAC_USER="ramonesnaola"
MAC_IP="10.164.1.26"
BACKUP_DIR="/Users/ramonesnaola/URA/backups_gx10"
SOURCE="/home/ramon/URA/ura_ia_1972"
LOG="/home/ramon/URA/logs/backup_mac.log"
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

log "=== Backup Mac ${TIMESTAMP} ==="

if ! ping -c 1 -W 3 "$MAC_IP" >/dev/null 2>&1; then
    log "ERROR: Mac ($MAC_IP) no alcanzable"
    exit 1
fi

rsync -avz --delete --bwlimit=10000 \
    --exclude="__pycache__" --exclude=".git" --exclude="*.pyc" \
    --exclude=".venv" --exclude=".nervioso" \
    "$SOURCE/" "${MAC_USER}@${MAC_IP}:${BACKUP_DIR}/" 2>&1 | tee -a "$LOG"

log "Backup Mac completado"
log "=== Fin ==="

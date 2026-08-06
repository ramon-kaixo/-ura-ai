#!/bin/bash
# Backup datos críticos Hetzner → ASUS + rotación 7 días
# EXPLÍCITAMENTE NO BACKUP (raw descargas): /root/ura_search/data/, /storage/inbox/
# Esos directorios contienen datos scrapeados de internet sin escanear.
# Si necesitas algo concreto, usa pull-from-hetzner.sh (escanea antes de traer).
HETZNER_HOST="100.78.49.106"
SSH_USER="ramon_admin"
SSH_KEY="$HOME/.ssh/id_ura_backup"
RSYNC_OPTS="-az --delete -e \"ssh -i $SSH_KEY -o StrictHostKeyChecking=no\" --rsync-path=\"sudo rsync\""
BACKUP_DIR="/home/ramon/URA/backups/hetzner"
LOG="/home/ramon/URA/logs/hetzner_backup.log"
RETENTION_DAYS=7

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG"; }
log "=== Backup Hetzner ==="

mkdir -p "$BACKUP_DIR/n8n" "$BACKUP_DIR/qdrant"

rsync -az --delete -e "ssh -i $SSH_KEY -o StrictHostKeyChecking=no" "$SSH_USER@$HETZNER_HOST:/opt/n8n/" "$BACKUP_DIR/n8n/" >> "$LOG" 2>&1 || log "n8n FAIL"
rsync -az --delete -e "ssh -i $SSH_KEY -o StrictHostKeyChecking=no" "$SSH_USER@$HETZNER_HOST:/opt/qdrant/storage/" "$BACKUP_DIR/qdrant/" >> "$LOG" 2>&1 || log "Qdrant FAIL"

# Rotación: mantener snapshot diario 7 días
SNAPSHOT="$BACKUP_DIR/snapshots/$(date '+%Y%m%d')"
mkdir -p "$SNAPSHOT"
cp -r "$BACKUP_DIR/n8n" "$SNAPSHOT/" 2>/dev/null
cp -r "$BACKUP_DIR/qdrant" "$SNAPSHOT/" 2>/dev/null
find "$BACKUP_DIR/snapshots" -maxdepth 1 -type d -mtime +$RETENTION_DAYS -exec rm -rf {} + 2>/dev/null

log "Backup: $(du -sh "$BACKUP_DIR" | cut -f1) | Snapshots: $(ls "$BACKUP_DIR/snapshots" 2>/dev/null | wc -l)"
log "=== Fin ==="

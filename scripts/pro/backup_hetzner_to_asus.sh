#!/bin/bash
# Backup datos críticos Hetzner → ASUS + rotación 7 días
HETZNER="root@178.105.81.83"
BACKUP_DIR="/home/ramon/URA/backups/hetzner"
LOG="/home/ramon/URA/logs/hetzner_backup.log"
RETENTION_DAYS=7

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG"; }
log "=== Backup Hetzner ==="

mkdir -p "$BACKUP_DIR/n8n" "$BACKUP_DIR/qdrant" "$BACKUP_DIR/scraper"

rsync -az --delete -e "ssh -o StrictHostKeyChecking=no" "$HETZNER:/opt/n8n/" "$BACKUP_DIR/n8n/" >> "$LOG" 2>&1 || log "n8n FAIL"
rsync -az --delete -e "ssh -o StrictHostKeyChecking=no" "$HETZNER:/opt/qdrant/storage/" "$BACKUP_DIR/qdrant/" >> "$LOG" 2>&1 || log "Qdrant FAIL"
rsync -az --delete -e "ssh -o StrictHostKeyChecking=no" "$HETZNER:/root/ura_search/data/" "$BACKUP_DIR/scraper/" >> "$LOG" 2>&1 || log "Scraper FAIL"

# Rotación: mantener snapshot diario 7 días
SNAPSHOT="$BACKUP_DIR/snapshots/$(date '+%Y%m%d')"
mkdir -p "$SNAPSHOT"
cp -r "$BACKUP_DIR/n8n" "$SNAPSHOT/" 2>/dev/null
cp -r "$BACKUP_DIR/qdrant" "$SNAPSHOT/" 2>/dev/null
find "$BACKUP_DIR/snapshots" -maxdepth 1 -type d -mtime +$RETENTION_DAYS -exec rm -rf {} + 2>/dev/null

log "Backup: $(du -sh "$BACKUP_DIR" | cut -f1) | Snapshots: $(ls "$BACKUP_DIR/snapshots" 2>/dev/null | wc -l)"
log "=== Fin ==="

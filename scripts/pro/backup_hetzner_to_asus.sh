#!/bin/bash
# Backup datos críticos de Hetzner → ASUS
HETZNER="root@178.105.81.83"
BACKUP_DIR="/home/ramon/URA/backups/hetzner"
LOG="/home/ramon/URA/logs/hetzner_backup.log"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG"; }
log "=== Backup Hetzner ==="
mkdir -p "$BACKUP_DIR/n8n" "$BACKUP_DIR/qdrant" "$BACKUP_DIR/scraper"
rsync -az --delete -e "ssh -o StrictHostKeyChecking=no" "$HETZNER:/opt/n8n/" "$BACKUP_DIR/n8n/" >> "$LOG" 2>&1 || log "n8n FAIL"
rsync -az --delete -e "ssh -o StrictHostKeyChecking=no" "$HETZNER:/opt/qdrant/storage/" "$BACKUP_DIR/qdrant/" >> "$LOG" 2>&1 || log "Qdrant FAIL"
rsync -az --delete -e "ssh -o StrictHostKeyChecking=no" "$HETZNER:/root/ura_search/data/" "$BACKUP_DIR/scraper/" >> "$LOG" 2>&1 || log "Scraper FAIL"
log "Backup: $(du -sh "$BACKUP_DIR" | cut -f1)"
log "=== Fin ==="

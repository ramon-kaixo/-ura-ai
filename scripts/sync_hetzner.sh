#!/bin/bash
set -euo pipefail
LOG="/home/ramon/URA/logs/sync_hetzner.log"
HETZNER="root@178.105.81.83"
DESTINO="/home/ramon/.nervioso/ura_search/cola/hetzner"
mkdir -p "$DESTINO"

log() { echo "[$(date)] $1" | tee -a "$LOG"; }

log "=== SINCRO HETZNER → GX10 ==="

# Sync Pinterest/Google data
rsync -avz --progress --partial "$HETZNER:/root/.nervioso/ura_search/cola/" "$DESTINO/" >> "$LOG" 2>&1

# Sync videos
rsync -avz --progress --partial "$HETZNER:/opt/ura/data/videos/" "/home/ramon/URA/data/videos/hetzner/" >> "$LOG" 2>&1

nuevos=$(find "$DESTINO" -type f -mmin -10 2>/dev/null | wc -l)
log "Sincronizados $nuevos archivos nuevos"
log "Total en destino: $(find "$DESTINO" -type f 2>/dev/null | wc -l)"

#!/bin/bash
set -euo pipefail

LOG="/home/ramon/URA/logs/sync_hetzner.log"
HETZNER_SSH="root@178.105.81.83"
HETZNER_TS="hetzner-escudo"
DESTINO="/home/ramon/.nervioso/ura_search/cola/hetzner"
VIDEO_DEST="/home/ramon/URA/data/videos/hetzner"
mkdir -p "$DESTINO" "$VIDEO_DEST"

log() { echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

log "=== SINCRO HETZNER → GX10 ==="

# 1. Scraped data from cola/
if ssh "$HETZNER_SSH" "test -d /root/.nervioso/ura_search/cola/"; then
    rsync -avz --partial --remove-source-files \
        "$HETZNER_SSH:/root/.nervioso/ura_search/cola/" "$DESTINO/" >> "$LOG" 2>&1
    log "Cola sincronizada"
else
    log "Directorio cola no existe en Hetzner"
fi

# 2. Videos
if ssh "$HETZNER_SSH" "test -d /opt/ura/data/videos/"; then
    rsync -avz --partial --remove-source-files \
        "$HETZNER_SSH:/opt/ura/data/videos/" "$VIDEO_DEST/" >> "$LOG" 2>&1
    log "Videos sincronizados"
else
    log "Directorio videos no existe en Hetzner"
fi

nuevos=$(find "$DESTINO" -type f -mmin -60 2>/dev/null | wc -l)
total=$(find "$DESTINO" -type f 2>/dev/null | wc -l)
log "Nuevos (60min): $nuevos | Total cola: $total"
log "=== FIN SINCRO ==="

#!/bin/bash
# =====================================================================
# filtro_cascada.sh — Filtro MIME/Tamaño/Hashing para N8N output
# Se ejecuta en Hetzner ANTES del rsync
# =====================================================================
set -e

INBOX="/root/.nervioso/ura_search/cola"
THRESHOLD_KB=100
LOG="/root/.nervioso/ura_search/filtro_cascada.log"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG"; }

for dir in "$INBOX"/*/; do
    [ -d "$dir" ] || continue
    for f in "$dir"*; do
        [ -f "$f" ] || continue
        
        # 1. Check tamaño
        SIZE_B=$(stat -c%s "$f" 2>/dev/null || echo 0)
        SIZE_KB=$((SIZE_B / 1024))
        
        # 2. Detectar MIME por magic bytes (sin librerías)
        MAGIC=$(xxd -p -l 4 "$f" 2>/dev/null | head -1)
        MIME="unknown"
        case "$MAGIC" in
            "ffd8ffe0"|"ffd8ffe1") MIME="image/jpeg" ;;
            "89504e47") MIME="image/png" ;;
            "25504446") MIME="application/pdf" ;;
            "3c21444f"|"3c68746d"|"3c68746d") MIME="text/html" ;;
            "7b5c7274"|"7b0a2022") MIME="application/json" ;;
        esac
        
        # 3. Comprimir si > threshold
        if [ "$SIZE_KB" -gt "$THRESHOLD_KB" ]; then
            zstd -1 -f "$f" -o "${f}.zst" 2>/dev/null && rm -f "$f"
            log "COMPRESSED: $f (${SIZE_KB}KB → $(( $(stat -c%s "${f}.zst" 2>/dev/null || echo 0) / 1024 ))KB, $MIME)"
        fi
        
        log "SCANNED: $f (${SIZE_KB}KB, $MIME)"
    done
done

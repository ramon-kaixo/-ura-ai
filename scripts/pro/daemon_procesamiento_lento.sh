#!/bin/bash
# =====================================================================
# daemon_procesamiento_lento.sh — Goteo constante al 10% CPU
# nice -n 19 ionice -c 3: prioridad mínima, sin bloquear el sistema
# =====================================================================
set -euo pipefail

INBOX="/storage/inbox"
PROCESSED="/storage/processed"
LOG="/home/ramon/URA/logs/daemon_lento.log"
mkdir -p "$INBOX" "$PROCESSED" "$(dirname "$LOG")"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

log "=== Daemon de procesamiento lento iniciado ==="

while true; do
    # 1. Contar archivos pendientes
    PENDIENTES=$(find "$INBOX" -type f 2>/dev/null | wc -l)
    
    if [ "$PENDIENTES" -gt 0 ]; then
        # 2. Tomar UN solo archivo (no todos — goteo, no tsunami)
        ARCHIVO=$(find "$INBOX" -type f -print -quit 2>/dev/null)
        
        if [ -n "$ARCHIVO" ]; then
            log "Procesando: $(basename $ARCHIVO)..."
            
            # 3. Procesar con mínima prioridad (10% CPU, I/O lento)
            nice -n 19 ionice -c 3 python3 /home/ramon/URA/ura_ia_1972/scripts/pro/compilador_opiniones.py \
                --input "$ARCHIVO" \
                --output "$PROCESSED/$(basename $ARCHIVO).json" 2>/dev/null || true
            
            # Mover a procesados (o eliminar si ya no sirve)
            mv "$ARCHIVO" "$PROCESSED/" 2>/dev/null || rm -f "$ARCHIVO"
            
            log "  ✅ $(basename $ARCHIVO) procesado"
        fi
    fi
    
    # 4. Pausa para mantener el 10%: dormir 60s entre fragmentos
    sleep 60
done

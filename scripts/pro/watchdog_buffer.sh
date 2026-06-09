#!/bin/bash
# =====================================================================
# watchdog_buffer.sh — Monitoriza buffer de 30GB en Hetzner
# Dispara procesamiento lento en GX10 cuando hay volumen suficiente
# =====================================================================
set -euo pipefail

BUFFER="/storage/inbox"
UMBRAL_MB=100       # Mínimo para empezar a procesar
UMBRAL_MAX_GB=28    # Máximo antes de alertar (30GB - margen)
LOG="/home/ramon/URA/logs/watchdog_buffer.log"
mkdir -p "$(dirname "$LOG")"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

log "=== Watchdog buffer iniciado ==="

while true; do
    if [ -d "$BUFFER" ]; then
        # 1. Medir tamaño del buffer
        TAMANO_MB=$(du -sm "$BUFFER" 2>/dev/null | cut -f1)
        ARCHIVOS=$(find "$BUFFER" -type f 2>/dev/null | wc -l)
        
        if [ "$TAMANO_MB" -gt "$UMBRAL_MAX_GB" ]; then
            log "⚠️  BUFFER CRITICO: ${TAMANO_MB}MB — cerca del límite de 30GB"
            # Forzar procesamiento urgente
            systemctl start ura-procesamiento-lento 2>/dev/null || true
            
        elif [ "$TAMANO_MB" -gt "$UMBRAL_MB" ]; then
            log "Buffer: ${TAMANO_MB}MB (${ARCHIVOS} archivos) — dentro del rango"
            # Asegurar que el daemon lento está corriendo
            systemctl is-active --quiet ura-procesamiento-lento || \
                systemctl start ura-procesamiento-lento 2>/dev/null || true
        fi
    fi
    
    sleep 120  # Revisar cada 2 minutos
done

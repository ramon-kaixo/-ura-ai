#!/bin/bash
# =====================================================================
# watcher_auditoria.sh — Monitoriza cola synced y dispara auditoría
# Usa inotify (sin polling) para detectar nuevos archivos
# =====================================================================
set -e

COLA="/home/ramon/.nervioso/ura_search/cola/hetzner"
LOG="/home/ramon/URA/logs/watcher_auditoria.log"
mkdir -p "$(dirname "$LOG")" "$COLA"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG"; }
log "=== Watcher iniciado ==="

# Bucle principal con inotify (o polling ligero si no hay inotify)
while true; do
    # Buscar archivos nuevos (últimos 5 minutos)
    NUEVOS=$(find "$COLA" -type f -mmin -5 2>/dev/null | wc -l)
    
    if [ "$NUEVOS" -gt 0 ]; then
        log "Detectados $NUEVOS archivos nuevos. Ejecutando auditoría..."
        bash /home/ramon/URA/ura_ia_1972/scripts/pro/auditoria_pesada.sh 2>&1 | tail -3
    fi
    
    sleep 60
done

#!/bin/bash
# ============================================================
# sync_workflow.sh — Flujo de trabajo completo Mac → ASUS
# Gestiona inmutabilidad, validación y sincronización
# ============================================================

MAC_DIR="/Users/ramonesnaola/URA/ura_ia_1972"
IMMUTABLE_SCRIPT="$MAC_DIR/deploy/immutable_mac.sh"
SYNC_SCRIPT="$MAC_DIR/deploy/sync_to_asus.sh"
LOG_FILE="$MAC_DIR/logs/sync_workflow.log"

mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "[$(date)] $1" >> "$LOG_FILE"
    echo "$1"
}

case "$1" in
    lock-and-sync)
        log "=== LOCK-AND-SYNC: Bloquear Mac + Sincronizar ==="
        # 1. Bloquear Mac
        log "Paso 1: Bloqueando Mac..."
        bash "$IMMUTABLE_SCRIPT" lock || { log "ERROR: No se pudo bloquear Mac"; exit 1; }
        
        # 2. Sincronizar (sync_to_asus.sh desbloquea temporalmente)
        log "Paso 2: Sincronizando..."
        bash "$SYNC_SCRIPT" || { log "ERROR: Sync falló"; exit 1; }
        
        log "=== LOCK-AND-SYNC COMPLETADO ==="
        ;;
    
    unlock-sync-lock)
        log "=== UNLOCK-SYNC-LOCK: Desbloquear + Sync + Rebloquear ==="
        # 1. Desbloquear manualmente
        log "Paso 1: Desbloqueando Mac manualmente..."
        bash "$IMMUTABLE_SCRIPT" unlock || { log "ERROR: No se pudo desbloquear"; exit 1; }
        
        # 2. Sincronizar
        log "Paso 2: Sincronizando..."
        bash "$SYNC_SCRIPT" || { log "ERROR: Sync falló"; exit 1; }
        
        # 3. Re-bloquear
        log "Paso 3: Re-bloqueando Mac..."
        bash "$IMMUTABLE_SCRIPT" lock || { log "ERROR: No se pudo re-bloquear"; exit 1; }
        
        log "=== UNLOCK-SYNC-LOCK COMPLETADO ==="
        ;;
    
    sync-only)
        log "=== SYNC-ONLY: Solo sincronizar (gestión automática) ==="
        bash "$SYNC_SCRIPT"
        ;;
    
    status)
        echo "=== ESTADO DEL SISTEMA ==="
        echo ""
        echo "Inmutabilidad Mac:"
        bash "$IMMUTABLE_SCRIPT" status
        echo ""
        echo "Conectividad ASUS:"
        if ping -c 1 -W 2 10.164.1.99 >/dev/null 2>&1; then
            echo "  ✓ ASUS alcanzable (10.164.1.99)"
        else
            echo "  ✗ ASUS NO alcanzable"
        fi
        ;;
    
    *)
        echo "Uso: $0 {lock-and-sync|unlock-sync-lock|sync-only|status}"
        echo ""
        echo "Comandos:"
        echo "  lock-and-sync    - Bloquea Mac, luego sincroniza (recomendado para producción)"
        echo "  unlock-sync-lock - Desbloquea, sincroniza, re-bloquea (para desarrollo)"
        echo "  sync-only        - Solo sincroniza (gestión automática de inmutabilidad)"
        echo "  status           - Muestra estado actual del sistema"
        echo ""
        echo "Flujo recomendado:"
        echo "  1. Desarrollo: unlock-sync-lock (permite ediciones entre syncs)"
        echo "  2. Producción: lock-and-sync (Mac siempre bloqueado)"
        echo "  3. Automatizado: sync-only (sync_to_asus.sh gestiona inmutabilidad)"
        exit 1
        ;;
esac

#!/bin/bash
# ============================================================
# clean_session_cache.sh — Limpieza segura de caché de sesión
# Limpia solo caché temporal sin perder configuración
# ============================================================

MAC_DIR="/Users/ramonesnaola/URA/ura_ia_1972"
ASUS_HOST="ramon@10.164.1.99"
ASUS_DIR="/home/ramon/URA/ura_ia_1972"
LOG_FILE="$MAC_DIR/logs/clean_session_cache.log"

mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "[$(date)] $1" >> "$LOG_FILE"
    echo "$1"
}

clean_mac() {
    log "=== LIMPIANDO CACHÉ EN MAC ==="
    
    # Limpiar __pycache__
    log "Limpiando __pycache__..."
    find "$MAC_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    log "  ✓ __pycache__ eliminado"
    
    # Limpiar .pytest_cache
    log "Limpiando .pytest_cache..."
    rm -rf "$MAC_DIR/.pytest_cache" 2>/dev/null || true
    log "  ✓ .pytest_cache eliminado"
    
    # Limpiar .ruff_cache
    log "Limpiando .ruff_cache..."
    rm -rf "$MAC_DIR/.ruff_cache" 2>/dev/null || true
    log "  ✓ .ruff_cache eliminado"
    
    log "=== MAC LIMPIADO ==="
}

clean_asus() {
    log "=== LIMPIANDO CACHÉ EN ASUS ==="
    
    # Verificar conectividad
    if ! ssh -o ConnectTimeout=5 "$ASUS_HOST" "echo ok" >/dev/null 2>&1; then
        log "ERROR: ASUS no alcanzable"
        return 1
    fi
    
    # Limpiar __pycache__
    log "Limpiando __pycache__ en ASUS..."
    ssh "$ASUS_HOST" "find '$ASUS_DIR' -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null" || true
    log "  ✓ __pycache__ eliminado en ASUS"
    
    # Limpiar .pytest_cache
    log "Limpiando .pytest_cache en ASUS..."
    ssh "$ASUS_HOST" "rm -rf '$ASUS_DIR/.pytest_cache' 2>/dev/null" || true
    log "  ✓ .pytest_cache eliminado en ASUS"
    
    # Limpiar .ruff_cache
    log "Limpiando .ruff_cache en ASUS..."
    ssh "$ASUS_HOST" "rm -rf '$ASUS_DIR/.ruff_cache' 2>/dev/null" || true
    log "  ✓ .ruff_cache eliminado en ASUS"
    
    # Limpiar .nervioso/audit_trail.log (solo log, no config)
    log "Limpiando .nervioso/audit_trail.log en ASUS..."
    ssh "$ASUS_HOST" "rm -f '$ASUS_DIR/.nervioso/audit_trail.log' 2>/dev/null" || true
    log "  ✓ audit_trail.log eliminado en ASUS"
    
    # Limpiar data/snapshots (solo snapshots temporales)
    log "Limpiando data/snapshots en ASUS..."
    ssh "$ASUS_HOST" "rm -rf '$ASUS_DIR/data/snapshots'/* 2>/dev/null" || true
    log "  ✓ snapshots limpiados en ASUS"
    
    # NO tocar: config/, data/documentos, data/openclaw_stats.json
    
    log "=== ASUS LIMPIADO ==="
}

case "$1" in
    mac)
        clean_mac
        ;;
    asus)
        clean_asus
        ;;
    both)
        clean_mac
        clean_asus
        ;;
    *)
        echo "Uso: $0 {mac|asus|both}"
        echo ""
        echo "Comandos:"
        echo "  mac   - Limpia solo caché en Mac"
        echo "  asus  - Limpia solo caché en ASUS"
        echo "  both  - Limpia caché en ambos nodos (recomendado)"
        echo ""
        echo "Archivos eliminados:"
        echo "  - __pycache__/ (ambos nodos)"
        echo "  - .pytest_cache/ (ambos nodos)"
        echo "  - .ruff_cache/ (ambos nodos)"
        echo "  - .nervioso/audit_trail.log (solo ASUS)"
        echo "  - data/snapshots/* (solo ASUS)"
        echo ""
        echo "Archivos PRESERVADOS:"
        echo "  - config/ (configuración)"
        echo "  - data/documentos/ (documentos)"
        echo "  - data/openclaw_stats.json (estadísticas)"
        echo "  - scripts/pro/.nervioso/watermarks.json (watermarks)"
        exit 1
        ;;
esac

log "=== LIMPIEZA COMPLETADA ==="

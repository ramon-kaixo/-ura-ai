#!/bin/bash
# ============================================================
# ura_watcher.sh — Watcher de cambios Mac → ASUS
# Usa fswatch (macOS) para detectar cambios y disparar sync.
# Ejecutar como daemon o launchd.
# ============================================================

URA_DIR="${URA_ROOT:-/Users/ramonesnaola/URA}/ura_ia_1972"
SYNC_SCRIPT="$URA_DIR/deploy/sync_to_asus.sh"
IMMUTABLE_SCRIPT="$URA_DIR/deploy/immutable_mac.sh"
LOG_FILE="$URA_DIR/logs/ura_watcher.log"
PID_FILE="/tmp/ura_watcher.pid"
DEBOUNCE_SECONDS=10

mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "[$(date)] $1" >> "$LOG_FILE"
}

# Verificar que fswatch está instalado
if ! command -v fswatch &> /dev/null; then
    log "ERROR: fswatch no instalado. Instalar: brew install fswatch"
    exit 1
fi

# Verificar que el sync script existe
if [ ! -f "$SYNC_SCRIPT" ]; then
    log "ERROR: sync_to_asus.sh no encontrado"
    exit 1
fi

# Función de debounce
last_sync=0
debounced_sync() {
    now=$(date +%s)
    diff=$((now - last_sync))
    if [ $diff -ge $DEBOUNCE_SECONDS ]; then
        log "Cambio detectado — ejecutando sync..."
        bash "$SYNC_SCRIPT" >> "$LOG_FILE" 2>&1
        last_sync=$now
    else
        log "Debounce: skip ($diff < ${DEBOUNCE_SECONDS}s)"
    fi
}

# Cleanup
cleanup() {
    log "Watcher detenido"
    rm -f "$PID_FILE"
    exit 0
}

trap cleanup SIGTERM SIGINT

# Iniciar
echo $$ > "$PID_FILE"
log "Watcher iniciado (PID $$)"
log "Monitoreando: $URA_DIR"
log "Sync script: $SYNC_SCRIPT"
log "Debounce: ${DEBOUNCE_SECONDS}s"

# Excluir directorios que no deben trigger sync
EXCLUDES=(
    "__pycache__"
    ".git"
    "node_modules"
    "*.pyc"
    ".URA_IMMUTABLE_STATE"
    ".URA_LOCKED"
    "logs/"
    "data/"
)

# Construir patrones de exclusión para fswatch
EXCLUDE_FLAGS=""
for exc in "${EXCLUDES[@]}"; do
    EXCLUDE_FLAGS="$EXCLUDE_FLAGS --exclude $exc"
done

# Monitorear cambios
fswatch -0 $EXCLUDE_FLAGS "$URA_DIR" | while read -d "" event; do
    debounced_sync
done

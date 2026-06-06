#!/usr/bin/env bash
# ============================================================
# Log Rotation — URA
# Comprime logs de > 7 dias y elimina los de > 30 dias.
# USO: ./mantenimiento/rotate_logs.sh
# ============================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"

# Directorios de logs (desde config)
LOG_DIRS=(
    "$HOME/URA/logs"
    "$HOME/URA/logs/maintenance"
)

DAYS_COMPRESS=7
DAYS_DELETE=30

compress_old() {
    local dir="$1"
    if [ ! -d "$dir" ]; then
        return
    fi
    find "$dir" -name "*.log" -mtime +"$DAYS_COMPRESS" -exec gzip -f {} \; 2>/dev/null
}

delete_ancient() {
    local dir="$1"
    if [ ! -d "$dir" ]; then
        return
    fi
    find "$dir" -name "*.log.gz" -mtime +"$DAYS_DELETE" -delete 2>/dev/null
    find "$dir" -name "maintenance_results_*.json" -mtime +"$DAYS_DELETE" -delete 2>/dev/null
    find "$dir" -name "remote_maintenance_results_*.json" -mtime +"$DAYS_DELETE" -delete 2>/dev/null
}

echo "URA Log Rotation"
echo "================"

for dir in "${LOG_DIRS[@]}"; do
    echo "  $dir"
    compress_old "$dir"
    delete_ancient "$dir"
done

echo "OK"

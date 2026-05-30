#!/bin/bash
# rotar_logs.sh – Comprime y purga logs antiguos de URA
REPO="${REPO:-$HOME/URA/ura_ia_1972}"

LOG_DIRS=(
    "$REPO/logs"
    "$REPO/logs/mejora_continua"
    "/var/log/ura_*.log"
    "/tmp/ura_*.log"
    "$HOME/ura_backup_inmortal/*.log"
    "$HOME/ura_backups/*.log"
)

COMPRESS_DAYS=7
DELETE_DAYS=14
LOG_FILE="$REPO/logs/rotacion.log"
mkdir -p "$(dirname "$LOG_FILE")"

echo "$(date) - Iniciando rotación de logs" >> "$LOG_FILE"

for pattern in "${LOG_DIRS[@]}"; do
    comprimidos=$(find $pattern -type f -name "*.log" -mtime +$COMPRESS_DAYS -exec gzip {} \; 2>/dev/null | wc -l)
    eliminados=$(find $pattern -type f -name "*.gz" -mtime +$DELETE_DAYS -delete 2>/dev/null | wc -l)
done

docker system prune -f --filter "until=168h" >> "$LOG_FILE" 2>&1 || true

echo "$(date) - Rotación completada" >> "$LOG_FILE"

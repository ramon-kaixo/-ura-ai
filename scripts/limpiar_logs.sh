#!/bin/bash
set -euo pipefail
LOG_DIR="/opt/ura/logs"
ARCHIVE_DIR="/opt/ura/logs/archivo"
mkdir -p "$ARCHIVE_DIR"

# Comprimir y mover logs con más de 30 días
find "$LOG_DIR" -name "*.log" -mtime +30 ! -path "*/archivo/*" -exec sh -c 'gzip -c "$1" > "$2/$(basename "$1").gz" && rm "$1"' _ {} "$ARCHIVE_DIR" \;

# Eliminar archivos comprimidos con más de 90 días
find "$ARCHIVE_DIR" -name "*.gz" -mtime +90 -delete

echo "$(date) - Limpieza de logs completada" >> "$LOG_DIR/limpieza.log"

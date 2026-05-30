#!/bin/bash
# limpiar_cuarentena.sh – Elimina archivos de cuarentena de más de 7 días

REPO="${REPO:-$HOME/URA/ura_ia_1972}"
CUARENTENA_DIR="$REPO/data/cuarentena"
LOG_FILE="$REPO/logs/cuarentena.log"
mkdir -p "$(dirname "$LOG_FILE")"

eliminados=$(find "$CUARENTENA_DIR" -name "*.lock" -mtime +7 -delete 2>/dev/null | wc -l)
echo "$(date) - Cuarentena limpiada: $eliminados archivos eliminados" >> "$LOG_FILE"

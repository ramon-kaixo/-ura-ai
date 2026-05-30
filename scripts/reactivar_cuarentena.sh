#!/bin/bash
# reactivar_cuarentena.sh – Elimina archivos de cuarentena de más de 12 horas
# Permite la reactivación automática de agentes aislados tras el periodo de enfriamiento

REPO="${REPO:-$HOME/URA/ura_ia_1972}"
CUARENTENA_DIR="$REPO/data/cuarentena"
LOG_FILE="$REPO/logs/cuarentena.log"
MIN_EDAD="${1:-720}"

mkdir -p "$(dirname "$LOG_FILE")"

eliminados=$(find "$CUARENTENA_DIR" -name "*.lock" -type f -mmin "+$MIN_EDAD" -delete 2>/dev/null | wc -l)
echo "$(date) - Reactivacion automatica: $eliminados locks eliminados (minima edad: ${MIN_EDAD}m)" >> "$LOG_FILE"

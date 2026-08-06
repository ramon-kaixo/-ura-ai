#!/bin/bash
# ciclo_rapido.sh – Auto-conciencia cada 5 min con bloqueo para evitar solapamiento

LOCK_FILE="/tmp/ura_conciencia.lock"
LOG="${HOME}/URA/ura_ia_1972/logs/ciclo_rapido.log"
REPO="${HOME}/URA/ura_ia_1972"
mkdir -p "$(dirname "$LOG")"

exec 200>"$LOCK_FILE"
flock -n 200 || { echo "$(date) - Ya en ejecucion. Saliendo." >> "$LOG"; exit 0; }

echo "$(date) - Iniciando ciclo rapido" >> "$LOG"
python3 "$REPO/scripts/pro/auto_conciencia.py" >> "$LOG" 2>&1
echo "$(date) - Ciclo rapido finalizado" >> "$LOG"

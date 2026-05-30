#!/bin/bash
# auto_heal_laia.sh — Autocuración de Laia API
# Si Laia se cuelga o su API deja de responder, la reinicia automáticamente.
# Añadir a crontab: */5 * * * * /path/to/scripts/auto_heal_laia.sh

set -euo pipefail

HEALTH_URL="${LAIA_HEALTH_URL:-http://localhost:8000/health}"
URA_BASE="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$URA_BASE/.venv"
LOG="/tmp/laia_auto_heal.log"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOG"
}

if curl -s --fail --max-time 10 "$HEALTH_URL" > /dev/null 2>&1; then
    log "OK Laia API responde"
    exit 0
fi

log "ERROR Laia API no responde, reiniciando..."

pkill -f "uvicorn laia_api:app" 2>/dev/null || true
sleep 2

cd "$URA_BASE"
source "$VENV/bin/activate" 2>/dev/null || true
nohup uvicorn laia_api:app --host 0.0.0.0 --port 8000 >> /tmp/laia_api.log 2>&1 &

sleep 3

if curl -s --fail --max-time 10 "$HEALTH_URL" > /dev/null 2>&1; then
    log "OK Laia API reiniciada correctamente"
else
    log "ERROR Laia API no arranco tras reinicio"
fi

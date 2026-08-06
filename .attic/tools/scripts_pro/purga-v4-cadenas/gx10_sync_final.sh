#!/bin/bash
# Sincronización Mac → GX10 + Tuneladora Pro
# Ejecutar desde el GX10
set -euo pipefail
MAC_IP="${TERMINAL_HOST:-10.164.1.26}"
MAC_USER="ramonesnaola"
REPO="${HOME}/URA/ura_ia_1972"
LOG="${HOME}/logs/gx10_sync.log"
mkdir -p "$(dirname "$LOG")"

echo "[$(date)] Sincronizando desde Mac..." >> "$LOG"
rsync -avz --exclude=.venv --exclude=__pycache__ --exclude=.git --exclude=quarantine \
  "${MAC_USER}@${MAC_IP}:${REPO}/" "${REPO}/" >> "$LOG" 2>&1

echo "[$(date)] Ejecutando Tuneladora Pro..." >> "$LOG"
cd "$REPO"
source .venv/bin/activate 2>/dev/null || true
bash scripts/pro/cross_trace.sh "gx10_sync" "iniciando"
bash scripts/pro/tuneladora_pro.sh >> "$LOG" 2>&1
bash scripts/pro/cross_trace.sh "gx10_pro" "completado"
echo "[$(date)] ✅ Ciclo completado" >> "$LOG"

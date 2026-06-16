#!/bin/bash
# deploy_to_hetzner.sh — Despliega los scripts de mineria remota a Hetzner.
# Uso: bash scripts/pro/deploy_to_hetzner.sh
# Requiere: SSH activo a hetzner (Port 2222)
set -euo pipefail

REMOTE_USER="root"
REMOTE_HOST="hetzner"
REMOTE_DIR="/home/ramon/scraping"
LOCAL_SCRAPING="/home/ramon/URA/ura_ia_1972/scraping"

echo "[DEPLOY] Verificando conexion SSH..."
ssh -o ConnectTimeout=10 "$REMOTE_HOST" "echo OK" || {
    echo "[ERROR] No se puede conectar a $REMOTE_HOST."
    exit 1
}

echo "[DEPLOY] Creando directorios remotos..."
ssh "$REMOTE_HOST" "mkdir -p $REMOTE_DIR/data"

echo "[DEPLOY] Subiendo meta_miner_remote.py..."
scp "$LOCAL_SCRAPING/meta_miner_remote.py" "${REMOTE_HOST}:${REMOTE_DIR}/meta_miner_remote.py"

echo "[DEPLOY] Verificando Python remoto..."
ssh "$REMOTE_HOST" "python3 --version"

echo "[DEPLOY] Test remoto: escaneando datos..."
ssh "$REMOTE_HOST" "python3 $REMOTE_DIR/meta_miner_remote.py $REMOTE_DIR/data" || {
    echo "[WARN] Test fallo (sin datos aun). No critico."
}

echo "[DEPLOY] Deploy completado. Ejecuta: bash scripts/pro/sync_knowledge.sh"

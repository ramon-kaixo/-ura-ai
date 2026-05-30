#!/bin/bash
set -euo pipefail
# backup_gx10_modelos.sh — Respaldar modelos de Ollama del GX10
GX10_HOST="${GX10_HOST:-10.164.1.99}"
GX10_USER="${GX10_USER:-root}"
BACKUP_DIR="${HOME}/backups/gx10/ollama"
TIMESTAMP=$(date +%Y%m%d)
mkdir -p "$BACKUP_DIR"

echo "   💾 Modelos GX10: $GX10_HOST"

MODELOS=$(ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new "${GX10_USER}@${GX10_HOST}" "ollama list 2>/dev/null | tail -n +2 | awk '{print \$1}'" 2>/dev/null || echo "")
[ -z "$MODELOS" ] && echo "   ⚠️ Sin conexion al GX10" && exit 0
echo "      $(echo "$MODELOS" | wc -l) modelos detectados"

ssh "${GX10_USER}@${GX10_HOST}" "tar czf /tmp/ollama_backup_${TIMESTAMP}.tar.gz -C /root/.ollama ." 2>/dev/null || true
scp -q "${GX10_USER}@${GX10_HOST}:/tmp/ollama_backup_${TIMESTAMP}.tar.gz" "${BACKUP_DIR}/ollama_${TIMESTAMP}.tar.gz" 2>/dev/null || true
ssh "${GX10_USER}@${GX10_HOST}" "rm -f /tmp/ollama_backup_${TIMESTAMP}.tar.gz" 2>/dev/null || true
find "$BACKUP_DIR" -name "ollama_*.tar.gz" -mtime +28 -delete 2>/dev/null || true

echo "   ✅ $(du -sh "${BACKUP_DIR}/ollama_${TIMESTAMP}.tar.gz" | awk '{print $1}')"

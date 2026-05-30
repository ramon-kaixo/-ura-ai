#!/bin/bash
set -euo pipefail
# backup_discos_locales.sh — Backup local hacia disco de 1 TB en GX10
ORIGEN="${HOME}/URA/ura_ia_1972"
DESTINO="/mnt/respaldo/backup_ura"
TIMESTAMP=$(date +%Y%m%d)
mkdir -p "$DESTINO" "/mnt/respaldo/models_backup" 2>/dev/null || true

echo "   Backup local: $DESTINO"

rsync -avz --delete "$ORIGEN/knowledge" "${DESTINO}/knowledge_${TIMESTAMP}" 2>/dev/null || true
rsync -avz --delete "$ORIGEN/scripts" "${DESTINO}/scripts_${TIMESTAMP}" 2>/dev/null || true
rsync -avz --delete "$ORIGEN/config" "${DESTINO}/config_${TIMESTAMP}" 2>/dev/null || true
tar czf "/mnt/respaldo/models_backup/ollama_${TIMESTAMP}.tar.gz" -C ~/.ollama . 2>/dev/null || true

find "$DESTINO" -type d -mtime +7 -exec rm -rf {} \; 2>/dev/null || true
find "/mnt/respaldo/models_backup" -type f -mtime +7 -delete 2>/dev/null || true

echo "   Backup local completado"

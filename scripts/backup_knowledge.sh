#!/bin/bash
set -euo pipefail
# backup_knowledge.sh — Backup semanal de la base de conocimiento
KNOWLEDGE_DIR="${HOME}/URA/ura_ia_1972/knowledge"
BACKUP_DIR="${HOME}/URA/ura_ia_1972/docs/backups"
TIMESTAMP=$(date +%Y%m%d)
BACKUP_FILE="${BACKUP_DIR}/knowledge_${TIMESTAMP}.tar.gz"
HETZNER_HOST="${HETZNER_BACKUP_HOST:-}"

mkdir -p "$BACKUP_DIR"

echo "💾 knowledge → ${BACKUP_FILE}"
tar czf "$BACKUP_FILE" -C "$(dirname "$KNOWLEDGE_DIR")" "$(basename "$KNOWLEDGE_DIR")" 2>/dev/null || true

if [ -n "$HETZNER_HOST" ]; then
    rsync -avz "$BACKUP_FILE" "${HETZNER_HOST}:/backups/ura/knowledge/" 2>/dev/null || true
    echo "   ☁️ Enviado al Hetzner"
fi

find "$BACKUP_DIR" -name "knowledge_*.tar.gz" -mtime +7 -delete 2>/dev/null || true
echo "✅ Backup: $(du -sh "$BACKUP_FILE" | awk '{print $1}')"

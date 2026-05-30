#!/bin/bash
set -euo pipefail
B2_BUCKET="${B2_BUCKET:-ura-backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="/tmp/ura_backup_${TIMESTAMP}.tar.gz"
echo "☁️ URA Backup — $TIMESTAMP"
tar -czf "$BACKUP_FILE" --exclude='.venv' --exclude='__pycache__' --exclude='quarantine' "${HOME}/.ura" "${HOME}/URA/ura_ia_1972/config" "${HOME}/URA/ura_ia_1972/docs/decisiones"
if command -v aws &>/dev/null; then
    aws s3 cp "$BACKUP_FILE" "s3://${B2_BUCKET}/daily/ura_backup_${TIMESTAMP}.tar.gz" --endpoint-url https://s3.us-west-002.backblazeb2.com --region us-west-002
    echo "✅ Backup subido"
else
    echo "⚠️  AWS CLI no instalado"
fi
find /tmp -name 'ura_backup_*.tar.gz' -mtime +7 -delete 2>/dev/null || true

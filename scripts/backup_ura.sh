#!/bin/bash
set -euo pipefail
# backup_ura.sh — Backup completo de URA (codigo + knowledge + config)
BACKUP_DIR="${HOME}/URA/ura_ia_1972/docs/backups"
TIMESTAMP=$(date +%Y%m%d)
BACKUP_FILE="${BACKUP_DIR}/ura_full_${TIMESTAMP}.tar.gz.gpg"
mkdir -p "$BACKUP_DIR"

echo "💾 Backup completo URA — $(date)"

# Knowledge
tar czf /tmp/ura_bk_knowledge.tar.gz -C "$HOME" "URA/ura_ia_1972/knowledge" 2>/dev/null || true
# Codigo (excluyendo venv y pycache)
tar czf /tmp/ura_bk_code.tar.gz -C "$HOME/URA/ura_ia_1972" \
    scripts agents config web core services sandbox \
    --exclude='*.pyc' --exclude='__pycache__' --exclude='.venv' 2>/dev/null || true
# Unificar y cifrar
cat /tmp/ura_bk_knowledge.tar.gz /tmp/ura_bk_code.tar.gz > /tmp/ura_bk_full.tar 2>/dev/null || true
gpg --encrypt --recipient "${GPG_RECIPIENT:-ramonesnaola}" \
    --output "$BACKUP_FILE" /tmp/ura_bk_full.tar 2>/dev/null

if [ -n "${HETZNER_BACKUP_HOST:-}" ]; then
    rsync -avz "$BACKUP_FILE" "${HETZNER_BACKUP_HOST}:/backups/ura/" 2>/dev/null || true
fi

find "$BACKUP_DIR" -name "ura_full_*.tar.gz.gpg" -mtime +7 -delete 2>/dev/null || true
rm -f /tmp/ura_bk_*

echo "OK $(du -sh "$BACKUP_FILE" | awk '{print $1}') cifrado"

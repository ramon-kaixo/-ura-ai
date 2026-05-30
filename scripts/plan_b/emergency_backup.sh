#!/bin/bash
set -euo pipefail
# Plan B — Backup de emergencia: comprime todo URA en un .tar.gz
BACKUP_DIR="${HOME}/URA/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
mkdir -p "$BACKUP_DIR"
echo "📦 Plan B: Backup de emergencia — $TIMESTAMP"
tar czf "${BACKUP_DIR}/ura_emergency_${TIMESTAMP}.tar.gz" \
  --exclude=.venv --exclude=__pycache__ --exclude=.git \
  --exclude=quarantine --exclude=logs \
  -C "${HOME}/URA" ura_ia_1972 2>/dev/null
echo "✅ Backup: ${BACKUP_DIR}/ura_emergency_${TIMESTAMP}.tar.gz"
echo "   Tamaño: $(du -h "${BACKUP_DIR}/ura_emergency_${TIMESTAMP}.tar.gz" | cut -f1)"

#!/bin/bash
set -euo pipefail
BACKUP_FILE="${1:-}"
[ -z "$BACKUP_FILE" ] && echo "Uso: restore.sh <backup.tar.gz>" && exit 1
[ ! -f "$BACKUP_FILE" ] && echo "🔴 Archivo no encontrado: $BACKUP_FILE" && exit 1
echo "📦 Plan B: Restaurando desde $BACKUP_FILE"
tar xzf "$BACKUP_FILE" -C "${HOME}/URA/"
echo "✅ Restaurado en ${HOME}/URA/ura_ia_1972"

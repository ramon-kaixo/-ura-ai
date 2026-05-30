#!/bin/bash
# backup_config.sh - Respalda configuraciones criticas de URA
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
BACKUP_DIR="${REPO}/backups/config"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

# Archivos a respaldar
FILES_TO_BACKUP=(
    "${REPO}/config/legal_rules.json"
    "${REPO}/config/tpv_endpoints.json"
    "${REPO}/config/gx10.json"
    "${REPO}/config/autonomia.json"
    "${REPO}/config/frigate.yml"
    "${REPO}/config/frigate_camaras_ejemplo.yml"
    "${REPO}/orquestador/maleta.json"
    "${REPO}/data"
    "${REPO}/knowledge"
    "${REPO}/macros"
)

# Crear archivo tar.gz
tar -czf "${BACKUP_DIR}/config_backup_${TIMESTAMP}.tar.gz" "${FILES_TO_BACKUP[@]}" 2>/dev/null || true

# Eliminar backups de mas de 30 dias
find "$BACKUP_DIR" -name "config_backup_*.tar.gz" -mtime +30 -delete 2>/dev/null || true

# Sincronizar con GX10 si esta disponible
if ssh -o ConnectTimeout=5 gx10 "echo ok" >/dev/null 2>&1; then
    scp "${BACKUP_DIR}/config_backup_${TIMESTAMP}.tar.gz" "gx10:/opt/ura/backups/" 2>/dev/null || true
    echo "   Backup sincronizado con GX10"
fi

echo "Backup completado: ${BACKUP_DIR}/config_backup_${TIMESTAMP}.tar.gz"

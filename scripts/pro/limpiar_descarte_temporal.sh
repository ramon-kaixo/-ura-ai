#!/usr/bin/env bash
# ==============================================================================
# limpiar_descarte_temporal.sh — Limpieza automática de la carpeta temporal de
# respaldos no versionados (/home/ramon/URA/descarte_temporal/).
#
# Borra archivos con más de 90 días SIN USO (atime/mtime/ctime) para no perder
# respaldos recientes mientras se libera espacio de forma segura.
#
# DEVOLUCIÓN: el respaldo es un safety-net temporal. Su contenido (providers v1,
# tests obsoletos, tar de no versionados) ya no se importa desde el repo; solo
# está por si acaso. Tras 90 días sin tocarse se considera que nadie lo necesita.
#
# ASOCIADO:
#   - Script:  scripts/pro/limpiar_descarte_temporal.sh
#   - Timer:   ura-descarte-temporal.timer / ura-descarte-temporal.service
#   - Carpeta: /home/ramon/URA/descarte_temporal/
#   - Docs:    docs/descarte_temporal.md
#
# USO:
#   ./limpiar_descarte_temporal.sh          # Ejecución normal
#   ./limpiar_descarte_temporal.sh --dry    # Solo informa, no borra
# ==============================================================================
set -euo pipefail

DEST="${DESCARTE_TEMPORAL:-/home/ramon/URA/descarte_temporal}"
DAYS=90
LOG_FILE="/var/log/limpiar_descarte_temporal.log"
DRY="${1:-}"

log() { echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

if [ ! -d "$DEST" ]; then
	log "Carpeta $DEST no existe. Nada que limpiar."
	exit 0
fi

log "=== Limpieza descarte temporal ($DEST) ==="

if [ "$DRY" = "--dry" ]; then
	log "(dry-run) Archivos con más de ${DAYS} días sin uso:"
	find "$DEST" -type f -mtime +${DAYS} -print
	log "(dry-run) Listo. No se borró nada."
	exit 0
fi

# Borrar archivos con más de $DAYS días de antigüedad sin uso.
find "$DEST" -type f -mtime +${DAYS} -delete
log "Limpieza completada: archivos con más de ${DAYS} días sin uso eliminados."

# Depurar directorios vacíos.
find "$DEST" -type d -empty -delete 2>/dev/null || true
log "Limpieza de directorios vacíos completada."

#!/bin/bash
# backup_toshiba.sh — Backup URA → disco externo Toshiba (NTFS)
# Uso: sudo bash scripts/backup_toshiba.sh
set -euo pipefail

DEVICE="/dev/sda2"
MOUNT="/mnt/toshiba"
SOURCE="/home/ramon/URA/ura_ia_1972"
DEST="$MOUNT/URA_GOLDEN_SNAPSHOT_JUN2026"
LOG="/home/ramon/URA/logs/backup_toshiba.log"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

log "=== Backup Toshiba ==="

if ! lsblk -no NAME "$DEVICE" >/dev/null 2>&1; then
    log "ERROR: $DEVICE no encontrado"
    exit 1
fi

sudo mkdir -p "$MOUNT"
if mountpoint -q "$MOUNT"; then
    log "OK: $MOUNT ya montado"
else
    sudo mount -t ntfs-3g "$DEVICE" "$MOUNT" 2>/dev/null || sudo mount -t ntfs "$DEVICE" "$MOUNT" 2>/dev/null || {
        log "ERROR: No se pudo montar $DEVICE (NTFS puede estar corrupto)"
        log "Ejecutar en Windows: chkdsk /f D:"
        exit 1
    }
    log "OK: $DEVICE montado en $MOUNT"
fi

sudo mkdir -p "$DEST"
log "Iniciando rsync..."
sudo rsync -av --delete --progress \
    --exclude="__pycache__" --exclude=".git" --exclude="*.pyc" \
    --exclude=".venv" --exclude=".nervioso" --exclude="*.log" \
    "$SOURCE/" "$DEST/" 2>&1 | tee -a "$LOG"

log "Backup completado. Tamaño: $(du -sh "$DEST" 2>/dev/null | cut -f1)"
sudo umount "$MOUNT" && log "OK: Disco desmontado"
log "=== Fin ==="

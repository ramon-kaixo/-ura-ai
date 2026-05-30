#!/bin/bash
# Script de backup automático para configuración de URA

BACKUP_DIR=~/Documents/URA_Backups/$(date +%Y%m%d)
mkdir -p "$BACKUP_DIR"

# Backup de configuraciones JSON
if [ -d ~/Desktop/URA_App/config ]; then
    cp ~/Desktop/URA_App/config/*.json "$BACKUP_DIR/" 2>/dev/null || echo "No hay archivos JSON en config/"
fi

# Backup de archivo .env
if [ -f ~/Desktop/URA_App/.env ]; then
    cp ~/Desktop/URA_App/.env "$BACKUP_DIR/"
fi

# Backup de permisos
if [ -f ~/.ura/permissions.json ]; then
    cp ~/.ura/permissions.json "$BACKUP_DIR/"
fi

echo "✅ Backup guardado en $BACKUP_DIR"
echo "📁 Archivos backup:"
ls -lh "$BACKUP_DIR"

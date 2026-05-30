#!/bin/bash
# Script de rollback a ADN inmutable

set -e

URA_APP=~/Desktop/URA_APP
URA_DNA=~/Desktop/URA_DNA
BACKUP_DIR=~/Desktop/URA_Backups

echo "🔄 Iniciando rollback a ADN inmutable..."

# 1. Crear backup del estado actual antes de rollback
echo "📦 Creando backup del estado actual..."
CURRENT_BACKUP="$BACKUP_DIR/rollback_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$CURRENT_BACKUP"
cp -r "$URA_APP" "$CURRENT_BACKUP/" || echo "⚠️  No se pudo crear backup"

# 2. Borrar instalación actual
echo "🗑️  Eliminando instalación actual..."
rm -rf "$URA_APP"

# 3. Restaurar desde ADN inmutable
echo "🧬 Restaurando desde ADN inmutable..."
cp -r "$URA_DNA" "$URA_APP"

# 4. Recrear entorno virtual
echo "🔧 Recreando entorno virtual..."
cd "$URA_APP"
python3.12 -m venv .venv
source .venv/bin/activate

# 5. Reinstalar dependencias
echo "📦 Reinstalando dependencias..."
if [ -f requirements.txt ]; then
    pip install -r requirements.txt
else
    pip install PyQt5 requests ollama redis
fi

# 6. Eliminar todos los parches (volver al estado puro del ADN)
echo "🧹 Eliminando parches..."
rm -f changes/*.patch

echo "✅ Rollback completado"
echo "📍 URA restaurado a estado ADN inmutable"
echo "📦 Backup del estado anterior: $CURRENT_BACKUP"

#!/bin/bash
# Script de construcción limpia desde ADN inmutable

set -e  # Fallar si algún comando falla

URA_APP=~/Desktop/URA_App
URA_DNA=~/Desktop/URA_DNA

echo "🧬 Reconstruyendo URA desde ADN inmutable..."

# 1. Backup rápido de instalación actual (si existe)
if [ -d "$URA_APP" ]; then
    BACKUP_DIR=~/Desktop/URA_Backups/$(date +%Y%m%d_%H%M%S)
    mkdir -p "$BACKUP_DIR"
    cp -r "$URA_APP" "$BACKUP_DIR/"
    echo "📦 Backup guardado en $BACKUP_DIR"
fi

# 2. Borrar instalación actual
echo "🗑️  Limpiando instalación actual..."
rm -rf "$URA_APP"

# 3. Copiar ADN (código base inmutable)
echo "🧬 Copiando ADN inmutable..."
cp -r "$URA_DNA" "$URA_APP"

# 4. Recrear entorno virtual
echo "🔧 Creando entorno virtual..."
cd "$URA_APP"
python3.12 -m venv .venv
source .venv/bin/activate

# 5. Instalar dependencias
echo "📦 Instalando dependencias..."
if [ -f requirements.txt ]; then
    pip install -r requirements.txt
else
    # Dependencias mínimas esenciales
    pip install PyQt5 requests ollama redis
fi

# 6. Crear directorios necesarios
echo "📁 Creando directorios..."
mkdir -p logs
mkdir -p scripts
mkdir -p changes

# 7. Aplicar parches aprobados (si existen)
if [ -d changes ] && [ "$(ls -A changes/*.patch 2>/dev/null)" ]; then
    echo "🔨 Aplicando parches aprobados..."
    for patch in changes/*.patch; do
        echo "   Aplicando: $(basename $patch)"
        patch -p1 < "$patch" || echo "   ⚠️  Falló aplicando $(basename $patch)"
    done
fi

echo "✅ Build limpio completado"
echo "📍 URA listo en: $URA_APP"
echo "🧬 ADN inmutable en: $URA_DNA (NO TOCAR)"

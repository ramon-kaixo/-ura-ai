#!/bin/bash
set -euo pipefail
# instalar_herramientas_sistema.sh — Instala herramientas de analisis de sistema
echo "   📦 Instalando herramientas..."

for pkg in clamav czkawka; do
    if ! command -v "$pkg" &>/dev/null && ! command -v "${pkg}_cli" &>/dev/null; then
        echo "      $pkg..."
        brew install "$pkg" 2>/dev/null || echo "      ⚠️ $pkg no disponible"
    else
        echo "      ✅ $pkg ya instalado"
    fi
done

if command -v freshclam &>/dev/null; then
    echo "      actualizando ClamAV..."
    freshclam 2>/dev/null || true
fi

echo "   ✅ Herramientas listas"

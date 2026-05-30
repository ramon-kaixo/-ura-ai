#!/bin/bash
set -euo pipefail
# instalar_herramientas_aps.sh — Instala herramientas de gestion de APs
echo "   📦 Herramientas APs..."

for pkg in linssid horst; do
    brew install "$pkg" 2>/dev/null || echo "      ⚠️ $pkg no disponible"
done

for repo in "kali/wavescope wavescope" "meterpreter/ghostbeacon ghostbeacon" "AsHfIEXE/SigVoid sigvoid" "confiback/confiback confiback"; do
    gh_user=$(echo "$repo" | awk '{print $1}')
    dir=$(echo "$repo" | awk '{print $2}')
    if [ ! -d "/opt/$dir" ]; then
        echo "      $dir..."
        git clone --depth=1 "https://github.com/$gh_user.git" "/opt/$dir" 2>/dev/null || true
        [ -f "/opt/$dir/requirements.txt" ] && pip install -q -r "/opt/$dir/requirements.txt" 2>/dev/null || true
    fi
done

pip install wifi-heat-mapper 2>/dev/null || true
echo "   ✅ Herramientas listas"

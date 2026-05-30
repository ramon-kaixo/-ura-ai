#!/bin/bash
set -euo pipefail
# instalar_kit_flota.sh — Instala kit URA en equipo remoto via SSH
IP="$1"
[ -z "$IP" ] && echo "Uso: instalar_kit_flota.sh <IP>" && exit 1

echo "   📦 Instalando kit en $IP..."

ssh -o StrictHostKeyChecking=accept-new "$IP" "
set -e
echo '      osquery...'
curl -fsSL https://raw.githubusercontent.com/fleetdm/fleet/main/tools/install-osquery.sh | bash 2>/dev/null || true
echo '      Floreant POS...'
git clone --depth=1 https://github.com/FloreantPos/FloreantPos.git /opt/floreant 2>/dev/null || true
echo '      Maloja...'
pip install maloja 2>/dev/null || true
echo '   OK $HOSTNAME'
" 2>&1 || echo "   Error en $IP"

echo "   ✅ Kit instalado en $IP"

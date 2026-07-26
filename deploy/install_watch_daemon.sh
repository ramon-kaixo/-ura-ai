#!/bin/bash
# Instala ura-watch-daemon.service como systemd system service
# Ejecutar DESPUÉS de reiniciar (rootfs RW)
set -euo pipefail

REPO="$HOME/URA/ura_ia_1972"
PREFLIGHT="$REPO/scripts/pro/tuneladora/preflight_system.py"

# Pre-flight check
if [ -f "$PREFLIGHT" ]; then
    echo "Ejecutando pre-flight check..."
    python3 "$PREFLIGHT" install ura-watch-daemon || {
        echo " PRE-FLIGHT: duplicado detectado — no se instalara"
        echo "Revisar deploy/system_manifest.json"
        exit 1
    }
fi

SERVICE="ura-watch-daemon.service"
SRC="$(dirname "$0")/$SERVICE"
DST="/etc/systemd/system/$SERVICE"

if [ ! -f "$SRC" ]; then
    echo "ERROR: $SRC no encontrado"
    exit 1
fi

echo "Instalando $SERVICE..."
sudo cp "$SRC" "$DST"
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE"
sudo systemctl start "$SERVICE"
sudo systemctl status "$SERVICE" --no-pager

echo ""
echo "LISTO. Logs: journalctl -u $SERVICE -f"

#!/bin/bash
set -euo pipefail
ERROR_LOG="/opt/ura/logs/launchd_errors.log"
SERVICIOS=("com.ura.mcp" "com.ura.nemoclaw")

for servicio in "${SERVICIOS[@]}"; do
    if ! launchctl list | grep -q "$servicio"; then
        echo "$(date) $servicio caido" >> "$ERROR_LOG"
        launchctl bootstrap gui/$(id -u) "/Library/LaunchAgents/${servicio}.plist" 2>/dev/null || true
    fi
done

for servicio in "${SERVICIOS[@]}"; do
    fallos=$(grep "$servicio caido" "$ERROR_LOG" 2>/dev/null | wc -l | tr -d ' ')
    if [ "${fallos:-0}" -ge 3 ]; then
        /opt/ura/scripts/notificar.sh "⚠️ $servicio ha fallado $fallos veces" 2>/dev/null || true
    fi
done

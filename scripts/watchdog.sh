#!/bin/bash
set -euo pipefail
HEARTBEAT="${HOME}/URA/ura_ia_1972/.heartbeat"
MAX_AGE=300
if [ -f "$HEARTBEAT" ]; then
    AGE=$(($(date +%s) - $(stat -f %m "$HEARTBEAT" 2>/dev/null || echo 0)))
    if [ "$AGE" -gt "$MAX_AGE" ]; then
        echo "🔴 Heartbeat obsoleto. Reiniciando..."
        pkill -f "registry_api.py" 2>/dev/null || true
        pkill -f "ura_dashboard.py" 2>/dev/null || true
        sleep 3
        cd "${HOME}/URA/ura_ia_1972"
        nohup python3 agents/registry_api.py &
        nohup python3 dashboard/ura_dashboard.py &
    fi
fi
if ! curl -s http://127.0.0.1:5100/agents &>/dev/null; then
    cd "${HOME}/URA/ura_ia_1972" && nohup python3 agents/registry_api.py &
fi
if ! curl -s http://127.0.0.1:5101 &>/dev/null; then
    cd "${HOME}/URA/ura_ia_1972" && nohup python3 dashboard/ura_dashboard.py &
fi

# Detectar intentos fallidos de montaje de red en Finder
LAST_SERVER=$(defaults read com.apple.finder FXConnectToLastURL 2>/dev/null || true)
if [ -n "$LAST_SERVER" ]; then
    SERVER_HOST=$(echo "$LAST_SERVER" | sed 's|smb://||; s|afp://||; s|/.*||; s|@.*||')
    if ! nc -z -w 2 "$SERVER_HOST" 445 2>/dev/null && ! nc -z -w 2 "$SERVER_HOST" 22 2>/dev/null; then
        osascript -e "display notification \"El Finder intenta conectar a $SERVER_HOST pero no responde. ¿Quieres que lo elimine?\" with title \"URA Alerta\" sound name \"Glass\"" 2>/dev/null
        echo "$(date '+%Y-%m-%d %H:%M:%S') [FINDER] Intento fallido de montaje: $LAST_SERVER" >> "${HOME}/URA/ura_ia_1972/logs/watchdog.log"
    fi
fi

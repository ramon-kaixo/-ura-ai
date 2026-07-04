#!/usr/bin/env bash
# start_contraste.sh — Arranque manual de proxy_contraste + watchdog
# Útil cuando root FS está en ro y systemd no puede levantar el servicio.
set -euo pipefail

PYTHON="/home/ramon/.local/bin/uvicorn"
APP="proxy_contraste:app"
WORKDIR="/opt/ura/agents"
PORT="8002"
LOG="/tmp/ura-contraste.log"

# Matar instancias previas
pkill -f "uvicorn proxy_contraste" 2>/dev/null || true
sleep 1

# Arrancar uvicorn (detached con setsid)
cd "$WORKDIR"
setsid "$PYTHON" "$APP" --host 0.0.0.0 --port "$PORT" --workers 1 \
  </dev/null &>"$LOG" &
UVICORN_PID=$!
echo "uvicorn PID: $UVICORN_PID"

# Esperar a que escuche
for i in $(seq 1 10); do
    if ss -tlnp 2>/dev/null | grep -q ":$PORT "; then
        echo "proxy_contraste escuchando en 0.0.0.0:$PORT"
        break
    fi
    sleep 1
done

# Si no escucha, abortar
if ! ss -tlnp 2>/dev/null | grep -q ":$PORT "; then
    echo "ERROR: uvicorn no arrancó en $PORT" >&2
    exit 1
fi

# Arrancar watchdog
WATCHDOG="/home/ramon/URA/ura_ia_1972/scripts/watchdog_contraste.py"
if [[ -f "$WATCHDOG" ]]; then
    setsid python3 "$WATCHDOG" </dev/null &>/tmp/ura-watchdog.log &
    echo "watchdog PID: $!"
fi

echo "OK: proxy_contraste + watchdog en ejecución"

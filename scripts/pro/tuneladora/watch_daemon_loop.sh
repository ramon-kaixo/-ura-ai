#!/bin/bash
# Wrapper: bucle de reinicio automático para watch_daemon.sh
# Arrancado por: systemd o nohup

REPO="$HOME/URA/ura_ia_1972"
LOCKFILE="/tmp/tuneladora_watch.lock"
WATCH_SCRIPT="$REPO/scripts/pro/tuneladora/watch_daemon.sh"

while true; do
    rm -f "$LOCKFILE"
    echo "[$(date '+%H:%M:%S')] Watch daemon iniciando..."
    bash "$WATCH_SCRIPT"
    echo "[$(date '+%H:%M:%S')] Watch daemon terminó inesperadamente, reiniciando en 3s..."
    sleep 3
done

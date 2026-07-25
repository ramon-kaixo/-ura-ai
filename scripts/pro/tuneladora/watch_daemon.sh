#!/bin/bash
# Watch daemon: ejecuta pipeline cuando detecta cambios en .py
# Uso: ./scripts/pro/tuneladora/watch_daemon.sh

REPO="$HOME/URA/ura_ia_1972"
PIPELINE="python3 $REPO/scripts/pro/tuneladora/tuneladora_pipeline.py"
DEBOUNCE_SEC=2
LOCKFILE="/tmp/tuneladora_watch.lock"

echo "[$(date '+%H:%M:%S')] Watch iniciado en $REPO"

inotifywait -m -r -e close_write --format '%w%f' "$REPO/scripts/pro/tuneladora" "$REPO/tests" 2>/dev/null | while read FILE; do
    # Solo archivos .py
    [[ "$FILE" == *.py ]] || continue
    
    # Debounce: esperar que pare de escribir
    sleep $DEBOUNCE_SEC
    
    # Mutex: si pipeline está corriendo, ignorar
    if [ -f "$LOCKFILE" ]; then
        echo "[$(date '+%H:%M:%S')] Pipeline ocupado, ignorando: $(basename $FILE)"
        continue
    fi
    
    # Crear lock
    touch "$LOCKFILE"
    
    echo "[$(date '+%H:%M:%S')] Cambio detectado: $(basename $FILE)"
    cd "$REPO"
    $PIPELINE --files "$FILE" --mode check 2>&1 | tail -5
    
    # Quitar lock
    rm -f "$LOCKFILE"
done

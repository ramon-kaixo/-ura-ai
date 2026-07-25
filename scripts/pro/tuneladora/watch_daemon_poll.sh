#!/bin/bash
# Watch daemon poll: ejecuta pipeline cuando detecta cambios en .py
# Usa polling (stat) en vez de inotify para funcionar con Samba/red.
# Uso: nohup bash scripts/pro/tuneladora/watch_daemon_poll.sh &
#      ./scripts/pro/tuneladora/watch_daemon.sh  (pasa a inotify si es local)

REPO="$HOME/URA/ura_ia_1972"
PIPELINE="python3 $REPO/scripts/pro/tuneladora/tuneladora_pipeline.py"
INTERVAL=3
STATE_FILE="/tmp/watch_poll_state.txt"
TEMP_FILE="/tmp/watch_poll_tmp.txt"
LOG_FILE="/tmp/watch_poll.log"
LOCKFILE="/tmp/tuneladora_watch.lock"

echo "[$(date '+%H:%M:%S')] Watch poll iniciado en $REPO (intervalo: ${INTERVAL}s)" >> "$LOG_FILE"

# Inicializar estado
touch "$STATE_FILE"

while true; do
    while IFS= read -r -d '' FILE; do
        MTIME=$(stat -c %Y "$FILE" 2>/dev/null || echo "0")
        if [ "$MTIME" = "0" ]; then
            continue
        fi

        # Leer estado anterior (path exacto)
        LAST_MTIME=$(grep -F "$FILE " "$STATE_FILE" 2>/dev/null | cut -d' ' -f2-)
        if [ -z "$LAST_MTIME" ]; then
            # Archivo nuevo: registrar sin ejecutar
            echo "$FILE $MTIME" >> "$STATE_FILE"
            continue
        fi

        if [ "$LAST_MTIME" != "$MTIME" ]; then
            echo "[$(date '+%H:%M:%S')] Cambio: $(basename "$FILE")" >> "$LOG_FILE"

            # Mutex: si pipeline está corriendo, ignorar
            if [ ! -f "$LOCKFILE" ]; then
                touch "$LOCKFILE"
                (
                    cd "$REPO" || exit 1
                    $PIPELINE --files "$FILE" --mode check >> "$LOG_FILE" 2>&1
                )
                rm -f "$LOCKFILE"
            else
                echo "[$(date '+%H:%M:%S')] Pipeline ocupado, ignorando: $(basename "$FILE")" >> "$LOG_FILE"
            fi
        fi

        # Actualizar estado: borrar entrada anterior + insertar nueva
        # Usar archivo temporal para evitar grep mismo archivo
        grep -Fv "$FILE " "$STATE_FILE" > "$TEMP_FILE" 2>/dev/null
        echo "$FILE $MTIME" >> "$TEMP_FILE"
        mv "$TEMP_FILE" "$STATE_FILE"
    done < <(find "$REPO/scripts/pro/tuneladora" "$REPO/tests" -name "*.py" -type f -print0 2>/dev/null)

    sleep "$INTERVAL"
done

#!/bin/bash
# Watch daemon: ejecuta pipeline cuando detecta cambios en .py
# Uso: ./scripts/pro/tuneladora/watch_daemon.sh
REPO="$HOME/URA/ura_ia_1972"
PIPELINE="python3 $REPO/scripts/pro/tuneladora/tuneladora_pipeline.py"
DEBOUNCE_SEC=2
COOLDOWN_SEC=10
LOCKFILE="/tmp/tuneladora_watch.lock"

_cleanup() {
    rm -f "$LOCKFILE"
}
trap _cleanup EXIT TERM INT
rm -f "$LOCKFILE"

echo "[$(date '+%H:%M:%S')] Watch iniciado en $REPO"

# Uso de process substitution para evitar subshell del pipe
while read FILE; do
    [[ "$FILE" == *.py ]] || continue
    sleep "$DEBOUNCE_SEC"

    # Lock atómico vía mkdir (operación atómica en Linux)
    if ! mkdir "$LOCKFILE.dir" 2>/dev/null; then
        echo "[$(date '+%H:%M:%S')] Pipeline ocupado, ignorando: $(basename "$FILE")"
        continue
    fi
    touch "$LOCKFILE"
    rmdir "$LOCKFILE.dir" 2>/dev/null || true

    echo "[$(date '+%H:%M:%S')] Cambio detectado: $(basename "$FILE")"
    cd "$REPO" || continue
    timeout 120 $PIPELINE --files "$FILE" --mode check 2>&1 | tail -5
    rm -f "$LOCKFILE"
    sleep "$COOLDOWN_SEC"
done < <(inotifywait -m -r -e close_write --format '%w%f' "$REPO/scripts/pro/tuneladora" "$REPO/tests" 2>/dev/null)

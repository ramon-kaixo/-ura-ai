#!/bin/bash
# Watch daemon v3.0 — con cola inteligente
# NO dispara si tuneladora esta corriendo. Encola 1 sola vez.
# Uso: ./scripts/pro/tuneladora/watch_daemon.sh

REPO="$HOME/URA/ura_ia_1972"
TUNELADORA_LOCK="$REPO/.tuneladora/lock"
PENDING_FILE="$REPO/.tuneladora/.watch_pending"
PIPELINE="python3 $REPO/scripts/pro/tuneladora/tuneladora_pipeline.py"
DEBOUNCE_SEC=2
COOLDOWN_SEC=10

# Funcion: verificar si tuneladora esta corriendo (lock valido)
_tuneladora_activa() {
    if [[ -f "$TUNELADORA_LOCK" ]]; then
        local pid
        pid=$(cat "$TUNELADORA_LOCK" 2>/dev/null | tr -d '\n')
        if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
            return 0
        fi
        rm -f "$TUNELADORA_LOCK"
    fi
    if [[ -f "$REPO/.tuneladora/lock.json" ]]; then
        local pid
        pid=$(python3 -c "import json; d=json.load(open('$REPO/.tuneladora/lock.json')); print(d.get('pid',''))" 2>/dev/null)
        if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
            return 0
        fi
        rm -f "$REPO/.tuneladora/lock.json"
    fi
    return 1
}

# Funcion: marcar pendiente
_marcar_pendiente() {
    echo "$1" > "$PENDING_FILE"
    echo "[$(date '+%H:%M:%S')] [COLA] Pendiente: $(basename "$1")"
}

# Funcion: procesar pendiente
_procesar_pendiente() {
    if [[ -f "$PENDING_FILE" ]]; then
        local file
        file=$(cat "$PENDING_FILE")
        rm -f "$PENDING_FILE"
        echo "[$(date '+%H:%M:%S')] [COLA] Procesando pendiente: $(basename "$file")"
        _ejecutar_pipeline "$file"
    fi
}

# Funcion: ejecutar pipeline
_ejecutar_pipeline() {
    local file="$1"
    cd "$REPO" || return
    echo "[$(date '+%H:%M:%S')] [RUN] $(basename "$file")"
    timeout 120 $PIPELINE --files "$file" --mode check 2>&1 | tail -5
    echo "[$(date '+%H:%M:%S')] [DONE] $(basename "$file")"
    sleep "$COOLDOWN_SEC"
    _procesar_pendiente
}

# PRE-FLIGHT
echo "[$(date '+%H:%M:%S')] Watch daemon v3.0 iniciado"
python3 "$REPO/scripts/pro/tuneladora/preflight_system.py" audit || {
    echo "[$(date '+%H:%M:%S')] PRE-FLIGHT: audit fallo — abortando"
    exit 1
}

rm -f "$PENDING_FILE"

# Loop principal
while read FILE; do
    [[ "$FILE" == *.py ]] || continue
    sleep "$DEBOUNCE_SEC"

    if _tuneladora_activa; then
        _marcar_pendiente "$FILE"
        continue
    fi

    _ejecutar_pipeline "$FILE"

done < <(inotifywait -m -r -e close_write --format '%w%f' "$REPO/scripts/pro/tuneladora" "$REPO/tests" 2>/dev/null)

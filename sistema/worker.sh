#!/bin/bash
set -euo pipefail
# worker.sh — Worker de tareas largas con cola FIFO y reintentos
QUEUE_DIR="/tmp/ura_queue"
MAX_RETRIES=3
LOG="/tmp/ura_worker.log"
mkdir -p "$QUEUE_DIR" "$QUEUE_DIR/failed"

echo "🔄 Worker iniciado — $(date)" >> "$LOG"

encolar() {
    local comando="$1"
    local id="tarea_$(date +%s)_$$"
    jq -n --arg cmd "$comando" '{comando: $cmd, intentos: 0}' > "${QUEUE_DIR}/${id}.job"
    echo "   📥 $id"
}

while true; do
    TAREA=$(ls -t "$QUEUE_DIR"/*.job 2>/dev/null | tail -1 || true)
    [ -z "$TAREA" ] && sleep 5 && continue

    CMD=$(jq -r '.comando // ""' "$TAREA" 2>/dev/null || echo "")
    INTENTOS=$(jq -r '.intentos // 0' "$TAREA" 2>/dev/null || echo 0)
    [ -z "$CMD" ] && rm -f "$TAREA" && continue

    NAME=$(basename "$TAREA" .job)
    echo "   ▶️ $NAME (intento $((INTENTOS + 1))/$MAX_RETRIES)" >> "$LOG"

    if eval "$CMD" >> "$LOG" 2>&1; then
        echo "   ✅ $NAME" >> "$LOG"
        rm -f "$TAREA"
    else
        INTENTOS=$((INTENTOS + 1))
        if [ "$INTENTOS" -ge "$MAX_RETRIES" ]; then
            echo "   🔴 $NAME fallo $MAX_RETRIES veces" >> "$LOG"
            mv "$TAREA" "$QUEUE_DIR/failed/" 2>/dev/null || true
            bash "${HOME}/URA/ura_ia_1972/scripts/notificar.sh" "Worker: $NAME fallo $MAX_RETRIES veces" error all 2>/dev/null || true
        else
            jq --argjson n "$INTENTOS" '.intentos = $n' "$TAREA" > "${TAREA}.tmp" 2>/dev/null && mv "${TAREA}.tmp" "$TAREA"
            echo "   🔄 $NAME reintento $INTENTOS/$MAX_RETRIES" >> "$LOG"
        fi
    fi
done

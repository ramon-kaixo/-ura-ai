#!/bin/bash
# Guarda en /tmp/opencode_bloqueo_*.log cuando OpenCode parece parado
LOGDIR="/tmp/opencode_monitoreo"
mkdir -p "$LOGDIR"
while true; do
    PID=$(pgrep -f "opencode web" | head -1)
    if [ -n "$PID" ]; then
        CPU=$(ps -p $PID -o %cpu= | tr -d ' ')
        if (( $(echo "$CPU < 1.0" | bc -l) )); then
            TS=$(date +%Y%m%d_%H%M%S)
            echo "=== BLOQUEO DETECTADO $TS ===" > "$LOGDIR/bloqueo_$TS.log"
            free -h >> "$LOGDIR/bloqueo_$TS.log"
            df -h /tmp >> "$LOGDIR/bloqueo_$TS.log"
            lsof -p $PID 2>/dev/null | wc -l >> "$LOGDIR/bloqueo_$TS.log"
            ls -la /proc/$PID/fd 2>/dev/null | wc -l >> "$LOGDIR/bloqueo_$TS.log"
            cat /proc/$PID/status 2>/dev/null | grep -E "State|VmRSS|Threads" >> "$LOGDIR/bloqueo_$TS.log"
        fi
    fi
    sleep 300
done

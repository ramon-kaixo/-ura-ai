#!/bin/bash
set -euo pipefail
URL="http://127.0.0.1:8087/health"
LOG="/opt/ura/logs/stress_test.log"
echo "$(date) - Iniciando prueba de estres" >> "$LOG"
la=$(curl -s -o /dev/null -w "%{time_total}" "$URL" 2>/dev/null || echo 0)
timeout 30 bash -c "while true; do curl -s $URL > /dev/null 2>&1; done" 2>/dev/null || true
ld=$(curl -s -o /dev/null -w "%{time_total}" "$URL" 2>/dev/null || echo 0)
echo "$(date) - Latencia: ${la}s -> ${ld}s" >> "$LOG"
if (( $(echo "$ld > 3 * $la" | bc -l 2>/dev/null || echo 0) )); then
    /opt/ura/scripts/notificar.sh "Degradacion en sandbox" 2>/dev/null || true
fi
echo "$(date) - Prueba completada" >> "$LOG"

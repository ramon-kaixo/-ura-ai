#!/bin/bash
set -euo pipefail
# buzo_mac.sh — Monitoriza la salud del Mac y registra metricas
MALETA="$1"; OUTPUT="$2"
REGISTRY_URL="${REGISTRY_URL:-http://127.0.0.1:5100}"
TMPFILE=$(mktemp); trap 'rm -f "$TMPFILE"' EXIT

echo "   🖥️ Mac metrics..."

CPU=$(top -l 2 -n 0 2>/dev/null | grep "CPU usage" | tail -1 | awk '{print $3}' | sed 's/%//' || echo 0)
echo "   📊 CPU: ${CPU}%"
echo "{\"buzo\":\"mac\",\"metrica\":\"cpu\",\"valor\":$CPU}" >> "$TMPFILE"

FREE=$(vm_stat 2>/dev/null | awk '/free/ {print $3}' | sed 's/\.//' || echo 0)
RAM=$((FREE * 4096 / 1024 / 1024))
echo "   🧠 RAM libre: ${RAM} MB"
echo "{\"buzo\":\"mac\",\"metrica\":\"ram_libre_mb\",\"valor\":$RAM}" >> "$TMPFILE"

DISCO=$(df -h / 2>/dev/null | tail -1 | awk '{print $5}' | sed 's/%//' || echo 0)
echo "   💾 Disco: ${DISCO}%"
echo "{\"buzo\":\"mac\",\"metrica\":\"disco_uso_pct\",\"valor\":$DISCO}" >> "$TMPFILE"

if command -v osx-cpu-temp &>/dev/null; then
    TEMP=$(osx-cpu-temp 2>/dev/null | grep -oE '^[0-9.]+' || echo "N/A")
    echo "   🌡️ Temp: ${TEMP}°C"
    [ "$TEMP" != "N/A" ] && echo "{\"buzo\":\"mac\",\"metrica\":\"temperatura_c\",\"valor\":$TEMP}" >> "$TMPFILE"
fi

for proc in "registry_api.py" "ura_dashboard.py" "health_api.py"; do
    if pgrep -f "$proc" >/dev/null 2>&1; then
        echo "{\"buzo\":\"mac\",\"proceso\":\"$(basename $proc .py)\",\"estado\":\"activo\"}" >> "$TMPFILE"
    else
        echo "{\"buzo\":\"mac\",\"proceso\":\"$(basename $proc .py)\",\"estado\":\"caido\"}" >> "$TMPFILE"
    fi
done

python3 -c "import json; items=[json.loads(l) for l in open('$TMPFILE') if l.strip()]; json.dump(items, open('$OUTPUT','w'), ensure_ascii=False, indent=2); print(len(items))" > /tmp/_mac_count 2>/dev/null || echo 0 > /tmp/_mac_count
echo "   ✅ $(cat /tmp/_mac_count) metricas"

# Registrar en Registry
ID="mac_monitor_$(date +%Y%m%d)"
curl -s -X POST "${REGISTRY_URL}/agents" -H "Content-Type: application/json" \
    -d "{\"id\":\"$ID\",\"type\":\"sistema\",\"cpu\":$CPU,\"ram_libre_mb\":$RAM,\"disco_uso_pct\":$DISCO,\"last_seen\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" >/dev/null 2>&1 || true

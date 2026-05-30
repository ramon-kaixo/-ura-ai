#!/bin/bash
set -euo pipefail
# buzo_flota.sh — Analiza dispositivos conectados via Tailscale
MALETA="$1"; OUTPUT="$2"
TAILSCALE_API_KEY="${TAILSCALE_API_KEY:-}"
REGISTRY_URL="${REGISTRY_URL:-http://127.0.0.1:5100}"
TMPFILE=$(mktemp); trap 'rm -f "$TMPFILE"' EXIT

[ -z "$TAILSCALE_API_KEY" ] && echo "   Configurar TAILSCALE_API_KEY" && echo "[]" > "$OUTPUT" && exit 0

echo "   🌐 Flota Tailscale..."
TAILNET=$(tailscale status --json 2>/dev/null | jq -r '.Self.DNSName' | sed 's/\.$//' || echo "")

DISPOSITIVOS=$(curl -s -H "Authorization: Bearer $TAILSCALE_API_KEY" \
    "https://api.tailscale.com/api/v2/tailnet/$TAILNET/devices" 2>/dev/null | \
    jq -c '.devices[]? | {id, hostname, os, ip: .addresses[0], online}' 2>/dev/null || echo "")

[ -z "$DISPOSITIVOS" ] && echo "   Sin dispositivos o API invalida" && echo "[]" > "$OUTPUT" && exit 0

echo "$DISPOSITIVOS" | while read -r dispositivo; do
    HOST=$(echo "$dispositivo" | jq -r '.hostname // "?"')
    OS=$(echo "$dispositivo" | jq -r '.os // "?"')
    IP=$(echo "$dispositivo" | jq -r '.ip // ""')
    ONLINE=$(echo "$dispositivo" | jq -r '.online // false')
    echo "   📡 $HOST ($OS, $IP) online=$ONLINE"

    if [ "$ONLINE" != "true" ]; then
        jq -c -n --arg host "$HOST" '{buzo: "flota", hostname: $host, estado: "offline"}' >> "$TMPFILE"
        continue
    fi

    [ -z "$IP" ] && jq -c -n --arg host "$HOST" '{buzo: "flota", hostname: $host, estado: "sin_ip"}' >> "$TMPFILE" && continue

    if ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=accept-new "$IP" "exit" 2>/dev/null; then
        DISCO=$(ssh "$IP" "df -h / 2>/dev/null | tail -1 | awk '{print \$5}' | sed 's/%//' || echo 0" 2>/dev/null || echo 0)
        RAM_TOTAL=$(ssh "$IP" "free -m 2>/dev/null | awk '/Mem/ {print \$2}' || echo 0" 2>/dev/null || echo 0)
        RAM_USADA=$(ssh "$IP" "free -m 2>/dev/null | awk '/Mem/ {print \$3}' || echo 0" 2>/dev/null || echo 0)
        PROCESOS=$(ssh "$IP" "ps aux --no-headers 2>/dev/null | wc -l || ps aux 2>/dev/null | wc -l" 2>/dev/null || echo 0)
        echo "     💾 Disco: ${DISCO}% | RAM: ${RAM_USADA}/${RAM_TOTAL} MB | Proc: ${PROCESOS}"
        jq -c -n --arg host "$HOST" --arg os "$OS" --arg ip "$IP" --argjson disco "$DISCO" --argjson ram "$RAM_USADA" --argjson ram_t "$RAM_TOTAL" --argjson proc "$PROCESOS" '{buzo: "flota", hostname: $host, os: $os, ip: $ip, estado: "online", disco_uso_pct: $disco, ram_usada_mb: $ram, ram_total_mb: $ram_t, procesos: $proc}' >> "$TMPFILE"
        curl -s -X POST "$REGISTRY_URL/agents" -H "Content-Type: application/json" \
            -d "{\"id\":\"flota_$HOST\",\"type\":\"dispositivo_tailscale\",\"ip\":\"$IP\",\"os\":\"$OS\",\"hostname\":\"$HOST\",\"last_seen\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" >/dev/null 2>&1 || true
    else
        echo "     🔴 Sin SSH"
        jq -c -n --arg host "$HOST" '{buzo: "flota", hostname: $host, estado: "online_sin_ssh"}' >> "$TMPFILE"
    fi
done

python3 -c "import json; items=[json.loads(l) for l in open('$TMPFILE') if l.strip()]; json.dump(items, open('$OUTPUT','w'), ensure_ascii=False, indent=2); print(len(items))" > /tmp/_flota_count 2>/dev/null || echo 0 > /tmp/_flota_count
echo "   ✅ $(cat /tmp/_flota_count) dispositivos"

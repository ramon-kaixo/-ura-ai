#!/bin/bash
set -euo pipefail
# buzo_camaras.sh — Descubre camaras RTSP nuevas y las configura en Frigate
MALETA="$1"; OUTPUT="$2"
SUBNET="${CAM_SUBNET:-}"
REGISTRY_URL="http://127.0.0.1:5100/agents"

# Auto-detectar subred
if [ -z "$SUBNET" ]; then
    SUBNET=$(ifconfig 2>/dev/null | grep "inet " | grep -v "127.0.0.1\|100\.\|10\.164" | awk '{print $2}' | head -1 | awk -F. '{print $1"."$2"."$3".0/24"}')
fi
echo "   🌐 Escaneando $SUBNET..."

IPS=$(nmap -sn "$SUBNET" -oG - 2>/dev/null | grep "Up$" | awk '{print $2}' || true)
[ -z "$IPS" ] && IPS=$(arp -a 2>/dev/null | awk '{print $2}' | tr -d '()' | head -30)

TMPFILE=$(mktemp); trap 'rm -f "$TMPFILE"' EXIT

for ip in $IPS; do
    # Verificar si el puerto RTSP esta abierto
    timeout 2 bash -c "echo > /dev/tcp/$ip/554" 2>/dev/null || continue
    # Verificar si ya esta registrada
    if curl -s "$REGISTRY_URL" 2>/dev/null | jq -e ".[] | select(.ip == \"$ip\")" >/dev/null 2>&1; then
        echo "   ⏩ $ip ya registrada"
        continue
    fi
    echo "   📷 Nueva camara en $ip"
    echo "{\"buzo\":\"camaras\",\"ip\":\"$ip\",\"estado\":\"nueva\"}" >> "$TMPFILE"
    # Registrar en Registry
    curl -s -X POST "$REGISTRY_URL" -H "Content-Type: application/json" \
        -d "{\"id\":\"cam_$ip\",\"type\":\"camara\",\"ip\":\"$ip\",\"port\":554,\"last_seen\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" >/dev/null 2>&1 || true
    # Configurar en Frigate (en segundo plano)
    bash "${HOME}/URA/ura_ia_1972/scripts/configurar_camara.sh" "$ip" &
done

python3 -c "import json; items=[json.loads(l) for l in open('$TMPFILE') if l.strip()]; json.dump(items, open('$OUTPUT','w'), ensure_ascii=False, indent=2); print(len(items))" > /tmp/_cam_count 2>/dev/null || echo 0 > /tmp/_cam_count
echo "✅ Buzo camaras: $(cat /tmp/_cam_count) nuevas"

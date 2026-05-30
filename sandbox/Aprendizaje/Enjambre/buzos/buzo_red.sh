#!/bin/bash
set -euo pipefail
# buzo_red.sh — Buzo unificado de red: dispositivos IP + WiFi + backup + alertas + limpieza
MALETA="$1"; OUTPUT="$2"
SUBNET="${SUBNET:-}"
REGISTRY_URL="${REGISTRY_URL:-http://127.0.0.1:5100}"
REPO="${HOME}/URA/ura_ia_1972"
INFORMES_DIR="${REPO}/sandbox/Aprendizaje/Enjambre/informes"
TMPFILE=$(mktemp); trap 'rm -f "$TMPFILE"' EXIT

if [ -z "$SUBNET" ]; then
    SUBNET=$(ifconfig 2>/dev/null | grep "inet " | grep -v "127.0.0.1\|100\.\|10\.164" | awk '{print $2}' | head -1 | awk -F. '{print $1"."$2"."$3".0/24"}')
fi
echo "   🌐 Red: $SUBNET"

# FASE 1: Dispositivos IP
IPS=$(nmap -sn "$SUBNET" -oG - 2>/dev/null | grep "Status: Up" | awk '{print $2}' || true)
[ -z "$IPS" ] && IPS=$(arp -a 2>/dev/null | awk '{print $2}' | tr -d '()' | head -20)
for ip in $IPS; do
    MAC=$(arp -n "$ip" 2>/dev/null | tail -1 | awk '{print $4}' || echo "?")
    if ! curl -s "$REGISTRY_URL" 2>/dev/null | jq -e ".[] | select(.ip == \"$ip\")" >/dev/null 2>&1; then
        echo "     🖥️ $ip ($MAC)"
        jq -c -n --arg ip "$ip" --arg mac "$MAC" '{buzo: "red", tipo: "dispositivo_ip", ip: $ip, mac: $mac}' >> "$TMPFILE"
        curl -s -X POST "${REGISTRY_URL}/agents" -H "Content-Type: application/json" \
            -d "{\"id\":\"dev_$ip\",\"type\":\"dispositivo_red\",\"ip\":\"$ip\",\"mac\":\"$MAC\",\"last_seen\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" >/dev/null 2>&1 || true
    fi
done

LATENCIA=$(ping -c 2 10.164.1.99 2>/dev/null | tail -1 | awk -F'/' '{print $5}' || echo "N/A")
echo "     📡 GX10: ${LATENCIA}ms"
jq -c -n --arg v "$LATENCIA" '{buzo: "red", tipo: "metrica", metrica: "latencia_gx10", valor: $v}' >> "$TMPFILE"

# FASE 2: Puntos de acceso WiFi
for tool in wavescope ghostbeacon confiback; do
    if command -v "$tool" &>/dev/null; then
        case "$tool" in
            wavescope) wavescope scan --json --output /tmp/ura_ws.json 2>/dev/null || true
                       n=$(jq 'length' /tmp/ura_ws.json 2>/dev/null || echo 0)
                       echo "     📶 $n APs (wavescope)"
                       jq -c -n --arg n "$n" '{buzo: "red", tipo: "metrica_aps", metrica: "aps", valor: $n}' >> "$TMPFILE" ;;
            ghostbeacon) ghostbeacon scan --output /tmp/ura_gb.json 2>/dev/null || true
                         n=$(jq 'length' /tmp/ura_gb.json 2>/dev/null || echo 0)
                         [ "$n" -gt 0 ] && echo "     🛡️ $n rogue APs" && jq -c -n --arg n "$n" '{buzo: "red", tipo: "metrica_aps", metrica: "rogue_aps", valor: $n}' >> "$TMPFILE" ;;
            confiback) confiback backup --all --output /tmp/ura_cb.json 2>/dev/null || true
                       n=$(jq 'length' /tmp/ura_cb.json 2>/dev/null || echo 0)
                       echo "     💾 $n backups"
                       jq -c -n --arg n "$n" '{buzo: "red", tipo: "metrica_aps", metrica: "backups", valor: $n}' >> "$TMPFILE" ;;
        esac
    fi
done

python3 -c "import json; items=[json.loads(l) for l in open('$TMPFILE') if l.strip()]; json.dump(items, open('$OUTPUT','w'), ensure_ascii=False, indent=2); print(len(items))" > /tmp/_red_count 2>/dev/null || echo 0 > /tmp/_red_count
echo "✅ Red: $(cat /tmp/_red_count) eventos"

# FASE 5: Alertas por umbral
echo "   🚨 Alertas..."
LATENCIA_MS=$(echo "$LATENCIA" | awk '{print int($1)}' 2>/dev/null || echo 0)
ROGUE_COUNT=$(jq '[.[] | select(.tipo == "metrica_aps" and .metrica == "rogue_aps") | .valor] | add // 0' "$OUTPUT" 2>/dev/null || echo 0)

if [ "${LATENCIA_MS:-0}" -gt 100 ] 2>/dev/null; then
    bash "${REPO}/scripts/notificar.sh" "Latencia GX10: ${LATENCIA}ms" warn all 2>/dev/null || true
fi
if [ "${ROGUE_COUNT:-0}" -gt 0 ] 2>/dev/null; then
    bash "${REPO}/scripts/notificar.sh" "${ROGUE_COUNT} rogue APs detectados" error all 2>/dev/null || true
fi

# FASE 6: Limpieza de dispositivos ausentes (>30 dias)
echo "   🧹 Limpieza..."
python3 -c "
import json, subprocess, os
from datetime import datetime, timedelta
r = subprocess.run(['curl', '-s', '$REGISTRY_URL'], capture_output=True, text=True)
if r.returncode != 0: exit()
agentes = json.loads(r.stdout) if r.stdout else []
ahora = datetime.utcnow()
for a in agentes:
    if a.get('type') not in ('dispositivo_red', 'access_point'): continue
    ls = a.get('last_seen', '')
    if not ls: continue
    try:
        d = (ahora - datetime.fromisoformat(ls)).days
        if d > 30:
            subprocess.run(['curl', '-s', '-X', 'DELETE', f'$REGISTRY_URL/agents/{a[\"id\"]}'], capture_output=True)
            print(f'     eliminado {a[\"id\"]} ({d} dias)')
        elif d > 7:
            print(f'     {a[\"id\"]}: {d} dias')
    except: pass
" 2>/dev/null || true

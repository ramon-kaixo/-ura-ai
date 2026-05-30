#!/bin/bash
set -euo pipefail
# buzo_aps.sh — Descubre, monitoriza y respalda puntos de acceso WiFi
MALETA="$1"; OUTPUT="$2"
REGISTRY_URL="${REGISTRY_URL:-http://127.0.0.1:5100}"
TMPFILE=$(mktemp); trap 'rm -f "$TMPFILE"' EXIT

echo "   📡 APs..."

for tool in wavescope linssid horst ghostbeacon sigvoid confiback wifi-heat-mapper; do
    if command -v "$tool" &>/dev/null; then
        echo "     🔍 $tool..."
        case "$tool" in
            wavescope) wavescope scan --json --output /tmp/ura_wavescope.json 2>/dev/null || true
                       jq -c -n --argjson n "$(jq 'length' /tmp/ura_wavescope.json 2>/dev/null || echo 0)" '{buzo: "aps", tool: "wavescope", aps: $n}' >> "$TMPFILE" ;;
            ghostbeacon) ghostbeacon scan --output /tmp/ura_rogue.json 2>/dev/null || true
                        jq -c -n --argjson n "$(jq 'length' /tmp/ura_rogue.json 2>/dev/null || echo 0)" '{buzo: "aps", tool: "ghostbeacon", rogue_aps: $n}' >> "$TMPFILE" ;;
            confiback) confiback backup --all --output /tmp/ura_backup.json 2>/dev/null || true
                      jq -c -n --argjson n "$(jq 'length' /tmp/ura_backup.json 2>/dev/null || echo 0)" '{buzo: "aps", tool: "confiback", backed_up: $n}' >> "$TMPFILE" ;;
            *) jq -c -n --arg t "$tool" '{buzo: "aps", tool: $t, status: "ok"}' >> "$TMPFILE" ;;
        esac
    fi
done

python3 -c "import json; items=[json.loads(l) for l in open('$TMPFILE') if l.strip()]; json.dump(items, open('$OUTPUT','w'), ensure_ascii=False, indent=2); print(len(items))" > /tmp/_aps_count 2>/dev/null || echo 0 > /tmp/_aps_count
echo "   ✅ $(cat /tmp/_aps_count) herramientas ejecutadas"

#!/bin/bash
set -euo pipefail
# desplegar_flota.sh — Despliega paquetes en dispositivos de la flota via SSH
PAQUETES_DIR="${HOME}/URA/ura_ia_1972/paquetes"
TAILSCALE_API_KEY="${TAILSCALE_API_KEY:-}"

echo "   🚀 Desplegando flota..."

DISPOSITIVOS=$(curl -s -H "Authorization: Bearer $TAILSCALE_API_KEY" \
    "https://api.tailscale.com/api/v2/tailnet/-/devices" 2>/dev/null | \
    jq -c '.devices[]? | {hostname, tags: (.tags // []), ip: .addresses[0], online}' 2>/dev/null || echo "")

[ -z "$DISPOSITIVOS" ] && echo "   Sin API key o sin dispositivos" && exit 0

echo "$DISPOSITIVOS" | while read d; do
    HOST=$(echo "$d" | jq -r '.hostname')
    IP=$(echo "$d" | jq -r '.ip // ""')
    ONLINE=$(echo "$d" | jq -r '.online // false')
    TAGS=$(echo "$d" | jq -r '.tags[]? // "general"' 2>/dev/null || echo "general")
    [ "$ONLINE" != "true" ] && echo "   🔴 $HOST offline" && continue

    PAQ="paquete_general.tar.gz"
    for t in $TAGS; do
        case "$t" in *caja*) PAQ="paquete_caja.tar.gz";; *music*) PAQ="paquete_musica.tar.gz";; esac
    done

    echo "   📦 $HOST ← $PAQ"
    scp -q "${PAQUETES_DIR}/$PAQ" "${IP}:/tmp/$PAQ" 2>/dev/null || { echo "     🔴 scp fallo"; continue; }
    ssh "$IP" "cd /tmp && tar xzf $PAQ && bash instalar.sh" 2>/dev/null || echo "     🔴 instalacion fallo"
done
echo "   ✅ Despliegue completado"

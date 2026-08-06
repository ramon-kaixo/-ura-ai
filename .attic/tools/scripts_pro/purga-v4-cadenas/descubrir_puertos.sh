#!/bin/bash
# descubrir_puertos.sh — Escanea puertos abiertos en todos los dispositivos Tailscale activos
# Dependencias: nmap, tailscale, jq

SCAN_DIR="/tmp/ura_scans"
mkdir -p "$SCAN_DIR"

echo "Descubriendo dispositivos activos en Tailscale..."

tailscale status --json 2>/dev/null | python3 -c "
import json, sys
d = json.load(sys.stdin)
for k, v in d.get('Peer', {}).items():
    ip = v.get('TailscaleIPs', [None])[0]
    name = v.get('HostName', '?')
    online = v.get('Online', False)
    if ip and online:
        print(f'{ip} {name}')
" > /tmp/ura_dispositivos_activos.txt

echo "Dispositivos activos encontrados:"
cat /tmp/ura_dispositivos_activos.txt

echo ""
echo "Escaneando puertos en cada dispositivo (paralelo)..."
while read -r ip name; do
    [ -z "$ip" ] && continue
    (
        out="$SCAN_DIR/scan_${ip}.txt"
        echo "  Escaneando $ip ($name)..."
        nmap -sT -p 1-10000 --open --min-rate=500 "$ip" -oG "$out" 2>/dev/null | tail -1
        echo "  Hecho: $ip"
    ) &
done < /tmp/ura_dispositivos_activos.txt
wait

echo ""
echo "=== Puertos descubiertos ==="
for f in "$SCAN_DIR"/scan_*.txt; do
    [ -f "$f" ] || continue
    ip=$(basename "$f" .txt | sed 's/scan_//')
    ports=$(grep "Ports:" "$f" | head -1 | sed 's/.*Ports: //' | sed 's/\/open.*//g' | tr ',' '\n' | awk '{print $1}' | tr '\n' ' ')
    [ -n "$ports" ] && echo "  $ip: $ports" || echo "  $ip: sin puertos abiertos (<10000)"
done

#!/bin/bash
# Rodillo -1: Filtro previo en el servidor (GX10)
set -euo pipefail

CLAM_AVAILABLE=false
if command -v clamscan &>/dev/null; then
    CLAM_AVAILABLE=true
else
    echo "⚠️  ClamAV no instalado. El escaneo antivirus se omite." >&2
fi

INBOX_SERVER="$HOME/Downloads/inbox_ura"
QUARANTINE="$HOME/quarantine_prefilter"
TRANSFER="$HOME/transfer_to_asus"
INVENTORY="$HOME/URA/ura_ia_1972/config/network_inventory.json"

mkdir -p "$QUARANTINE" "$TRANSFER"
shopt -s nullglob

for file in "$INBOX_SERVER"/*; do
    [ -f "$file" ] || continue
    echo "Pre-filtrando: $(basename "$file")"

    # 1. Escaneo antivirus
    if [ "$CLAM_AVAILABLE" = true ]; then
        if ! clamscan --quiet --no-summary "$file"; then
            mv "$file" "$QUARANTINE/"
            echo "🔴 Virus detectado en $(basename "$file") — cuarentena"
            continue
        fi
    fi

INBOX_SERVER="$HOME/Downloads/inbox_ura"
QUARANTINE="$HOME/quarantine_prefilter"
TRANSFER="$HOME/transfer_to_asus"
INVENTORY="$HOME/URA/ura_ia_1972/config/network_inventory.json"

mkdir -p "$QUARANTINE" "$TRANSFER"
shopt -s nullglob

for file in "$INBOX_SERVER"/*; do
    [ -f "$file" ] || continue
    echo "Pre-filtrando: $(basename "$file")"

    if ! clamscan --quiet --no-summary "$file"; then
        mv "$file" "$QUARANTINE/"
        echo "🔴 Virus en $(basename "$file") — cuarentena"
        continue
    fi

    HASH=$(sha256sum "$file" | cut -d' ' -f1)
    if [ -f "$HOME/blacklist_hashes.txt" ] && grep -q "$HASH" "$HOME/blacklist_hashes.txt"; then
        mv "$file" "$QUARANTINE/"
        echo "🔴 Hash bloqueado: $(basename "$file")"
        continue
    fi

    if [[ "$file" == *.py ]] || [[ "$file" == *.json ]]; then
        python3 -c "
import json, re, sys
with open('$INVENTORY') as f:
    inv = json.load(f)
with open('$file') as f:
    content = f.read()
ips = re.findall(r'\d+\.\d+\.\d+\.\d+', content)
ports = re.findall(r'port\s*[=:]\s*(\d+)', content)
for ip in ips:
    if ip in inv.get('ips_in_use', []):
        print(f'IP conflictiva: {ip}')
        sys.exit(1)
for p in ports:
    if int(p) in inv.get('ports_in_use', []):
        print(f'Puerto conflictivo: {p}')
        sys.exit(1)
" 2>/dev/null
        if [ $? -ne 0 ]; then
            mv "$file" "$QUARANTINE/"
            echo "🔴 Conflicto con inventario: $(basename "$file")"
            continue
        fi
    fi

    mv "$file" "$TRANSFER/"
    echo "✅ Pasó prefiltro: $(basename "$file") listo para ASUS"
done

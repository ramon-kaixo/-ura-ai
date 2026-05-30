#!/bin/bash
# buzo_inventario.sh - Inventario de software en toda la flota
# Ejecuta: cada 24h (cron) o bajo demanda
# Guarda en: /opt/ura/data/software_inventario.json
set -e
REGISTRO="/opt/ura/data/software_inventario.json"
TEMP="/tmp/inventario_$$.txt"
LOG="/opt/ura/logs/buzo_inventario.log"
echo "[$(date)] Inventario iniciado" >> "$LOG"

echo "=== MAC MINI (local) ===" > "$TEMP"
echo "--- Brew formulas ---" >> "$TEMP"
brew list --versions 2>/dev/null >> "$TEMP" || echo "brew no disponible"
echo "--- Pip packages ---" >> "$TEMP"
pip3 list --format=freeze 2>/dev/null >> "$TEMP" || echo "pip no disponible"
echo "--- Scripts URA ---" >> "$TEMP"
find /opt/ura -name "*.py" -o -name "*.sh" -o -name "*.js" 2>/dev/null | head -100 >> "$TEMP"
echo "--- LaunchAgents ---" >> "$TEMP"
ls ~/Library/LaunchAgents/com.ura* 2>/dev/null >> "$TEMP"

echo "=== GX10 (10.164.1.99) ===" >> "$TEMP"
ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no ramon@10.164.1.99 "
  echo '--- Apt packages ---'
  dpkg-query -W --showformat='\${Package}\n' 2>/dev/null | head -50
  echo '--- Pip ---'
  pip3 list --format=freeze 2>/dev/null | head -50
  echo '--- Docker ---'
  docker ps --format '{{.Names}}' 2>/dev/null
" >> "$TEMP" 2>/dev/null || echo "GX10 no accesible" >> "$TEMP"

echo "=== TPVs ===" >> "$TEMP"
for tpv in caja0 100.127.217.113; do
  echo "--- $tpv ---" >> "$TEMP"
  ssh -o ConnectTimeout=3 -o StrictHostKeyChecking=no "root@$tpv" "
    wmic product get name 2>/dev/null | head -30
  " >> "$TEMP" 2>/dev/null || echo "$tpv no accesible" >> "$TEMP"
done

python3 -c "
import json, time
with open('$TEMP') as f:
    lines = [l.strip() for l in f if l.strip()]
with open('$REGISTRO', 'w') as f:
    json.dump({'timestamp': time.time(), 'software': lines, 'total': len(lines)}, f, indent=2)
"
rm -f "$TEMP"
echo "[$(date)] ✅ Inventario guardado: $(jq '.total' "$REGISTRO") items" >> "$LOG"
echo "Inventario completado: $(jq '.total' "$REGISTRO") items"

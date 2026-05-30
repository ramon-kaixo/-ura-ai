#!/bin/bash
set -euo pipefail
# buzo_sistema.sh — Analiza, limpia y protege el sistema operativo
MALETA="$1"; OUTPUT="$2"
REGISTRY_URL="${REGISTRY_URL:-http://127.0.0.1:5100}"
HOME_DIR="${HOME}"
TMPFILE=$(mktemp); trap 'rm -f "$TMPFILE"' EXIT
SCAN_DIRS="$HOME_DIR/URA $HOME_DIR/Downloads $HOME_DIR/Desktop"

echo "   🖥️ Sistema..."
DISCO_PCT=$(df -h / 2>/dev/null | tail -1 | awk '{print $5}' | sed 's/%//' || echo 0)
DISCO_USADO=$(df -h / 2>/dev/null | tail -1 | awk '{print $3}' || echo "?")
DISCO_TOTAL=$(df -h / 2>/dev/null | tail -1 | awk '{print $2}' || echo "?")
echo "   💾 $DISCO_USADO de $DISCO_TOTAL (${DISCO_PCT}%)"
echo "{\"buzo\":\"sistema\",\"metrica\":\"disco_uso_pct\",\"valor\":$DISCO_PCT}" >> "$TMPFILE"

GRANDES=$(find $SCAN_DIRS -type f -size +100M -not -path "*/node_modules/*" -not -path "*/.venv/*" -maxdepth 5 2>/dev/null | wc -l | tr -d ' ')
echo "   📦 $GRANDES archivos >100MB"
echo "{\"buzo\":\"sistema\",\"metrica\":\"archivos_grandes\",\"valor\":$GRANDES}" >> "$TMPFILE"

if command -v czkawka_cli &>/dev/null; then
    czkawka_cli dup --directories "$HOME_DIR/URA" --search-method hash --delete-method none -o /tmp/ura_dup.txt 2>/dev/null || true
    DUP=$(wc -l < /tmp/ura_dup.txt 2>/dev/null || echo 0)
    echo "   🗑️ $DUP duplicados"
else
    echo "   ⚠️ czkawka no instalado (brew install czkawka)"
    DUP=0
fi
echo "{\"buzo\":\"sistema\",\"metrica\":\"duplicados\",\"valor\":$DUP}" >> "$TMPFILE"

TEMP_SIZE=$(find /tmp -type f -mtime +7 2>/dev/null | wc -l | tr -d ' ')
echo "   🧹 $TEMP_SIZE temporales >7 dias"
echo "{\"buzo\":\"sistema\",\"metrica\":\"temporales_antiguos\",\"valor\":$TEMP_SIZE}" >> "$TMPFILE"

python3 -c "import json; items=[json.loads(l) for l in open('$TMPFILE') if l.strip()]; json.dump(items, open('$OUTPUT','w'), ensure_ascii=False, indent=2); print(len(items))" > /tmp/_sistema_count 2>/dev/null || echo 0 > /tmp/_sistema_count
echo "   ✅ $(cat /tmp/_sistema_count) metricas"

curl -s -X POST "${REGISTRY_URL}/agents" -H "Content-Type: application/json" \
    -d "{\"id\":\"sistema_monitor\",\"type\":\"sistema\",\"disco_uso_pct\":$DISCO_PCT,\"archivos_grandes\":$GRANDES,\"last_seen\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" >/dev/null 2>&1 || true

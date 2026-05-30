#!/bin/bash
set -euo pipefail
MALETA="$1"; OUTPUT="$2"
SEARXNG_URL="${SEARXNG_URL:-http://178.105.81.83:8888}"
FOODISH="https://foodish-api.herokuapp.com/api"
TMPFILE=$(mktemp); trap 'rm -f "$TMPFILE"' EXIT
jq -r '.cocina.categorias_fotos[]' "$MALETA" 2>/dev/null | while IFS= read -r cat; do
    [ -z "$cat" ] && continue
    echo "   📷 $cat"
    curl -s --max-time 10 "${FOODISH}/images/${cat}" 2>/dev/null | jq -c --arg cat "$cat" '.[]? | {buzo: "fotos", categoria: $cat, url: ., fuente: "Foodish"}' 2>/dev/null >> "$TMPFILE"
done
python3 -c "import json; items=[json.loads(l) for l in open('$TMPFILE') if l.strip()]; json.dump(items, open('$OUTPUT','w'), ensure_ascii=False, indent=2); print(len(items))" > /tmp/_fotos_count 2>/dev/null || echo 0 > /tmp/_fotos_count
echo "   ✅ $(cat /tmp/_fotos_count) fotos"

#!/bin/bash
set -euo pipefail
MALETA="$1"; OUTPUT="$2"
SEARXNG_URL="${SEARXNG_URL:-http://178.105.81.83:8888}"
TMPFILE=$(mktemp); trap 'rm -f "$TMPFILE"' EXIT
jq -r '.competencia.restaurantes[]' "$MALETA" 2>/dev/null | while IFS= read -r competidor; do
    [ -z "$competidor" ] && continue
    echo "   📊 $competidor"
    QUERY=$(python3 -c "import sys,urllib.parse; print(urllib.parse.quote(' '.join(sys.argv[1:])))" $competidor 2>/dev/null)
    curl -s --max-time 15 "${SEARXNG_URL}/search?q=${QUERY}&format=json&time_range=month&language=es&safesearch=2&category=news" 2>/dev/null | \
        jq -c --arg competidor "$competidor" '.results[]? | {buzo: "competencia", restaurante: $competidor, titulo: .title, url: .url}' 2>/dev/null >> "$TMPFILE" || echo "   ⚠️ Sin datos: $competidor" >&2
done
python3 -c "import json; items=[json.loads(l) for l in open('$TMPFILE') if l.strip()]; json.dump(items, open('$OUTPUT','w'), ensure_ascii=False, indent=2); print(len(items))" > /tmp/_comp_count 2>/dev/null || echo 0 > /tmp/_comp_count
echo "   ✅ $(cat /tmp/_comp_count) menciones"

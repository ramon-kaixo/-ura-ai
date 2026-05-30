#!/bin/bash
set -euo pipefail
MALETA="$1"; OUTPUT="$2"
SEARXNG_URL="${SEARXNG_URL:-http://178.105.81.83:8888}"
TMPFILE=$(mktemp); trap 'rm -f "$TMPFILE"' EXIT
jq -r '.economia.busquedas[]' "$MALETA" 2>/dev/null | while IFS= read -r busqueda; do
    [ -z "$busqueda" ] && continue; echo "   📊 $busqueda"
    QUERY=$(python3 -c "import sys,urllib.parse; print(urllib.parse.quote(' '.join(sys.argv[1:])))" $busqueda 2>/dev/null)
    curl -s --max-time 15 "${SEARXNG_URL}/search?q=${QUERY}&format=json&time_range=month&language=es&safesearch=2&category=news" 2>/dev/null | \
        jq -c --arg busqueda "$busqueda" '.results[]? | {buzo: "economia", tema: $busqueda, titulo: .title, url: .url}' 2>/dev/null >> "$TMPFILE" || echo "   ⚠️ Sin datos: $busqueda" >&2
done
python3 -c "import json; items=[json.loads(l) for l in open('$TMPFILE') if l.strip()]; json.dump(items, open('$OUTPUT','w'), ensure_ascii=False, indent=2); print(len(items))" > /tmp/_eco_count 2>/dev/null || echo 0 > /tmp/_eco_count
echo "✅ Buzo de economia: $(cat /tmp/_eco_count) noticias"

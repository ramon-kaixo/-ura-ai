#!/bin/bash
set -euo pipefail
MALETA="$1"; OUTPUT="$2"
SEARXNG_URL="${SEARXNG_URL:-http://178.105.81.83:8888}"
TMPFILE=$(mktemp); trap 'rm -f "$TMPFILE"' EXIT
jq -r '.prensa_diaria.eventos[]' "$MALETA" 2>/dev/null | while IFS= read -r tema; do
    [ -z "$tema" ] && continue; echo "   📰 $tema"
    QUERY=$(python3 -c "import sys,urllib.parse; print(urllib.parse.quote(' '.join(sys.argv[1:])))" $tema 2>/dev/null)
    curl -s --max-time 15 "${SEARXNG_URL}/search?q=${QUERY}&format=json&time_range=day&language=es&safesearch=2&category=news" 2>/dev/null | \
        jq -c --arg tema "$tema" '.results[]? | {buzo: "prensa_diaria", tipo: "evento", tema: $tema, titulo: .title, url: .url}' 2>/dev/null >> "$TMPFILE" || echo "   ⚠️ Sin datos: $tema" >&2
done
jq -r '.prensa_diaria.tendencias[]' "$MALETA" 2>/dev/null | while IFS= read -r tema; do
    [ -z "$tema" ] && continue; echo "   🔮 $tema"
    QUERY=$(python3 -c "import sys,urllib.parse; print(urllib.parse.quote(' '.join(sys.argv[1:])))" $tema 2>/dev/null)
    curl -s --max-time 15 "${SEARXNG_URL}/search?q=${QUERY}&format=json&time_range=week&language=es&safesearch=2&category=news" 2>/dev/null | \
        jq -c --arg tema "$tema" '.results[]? | {buzo: "prensa_diaria", tipo: "tendencia", tema: $tema, titulo: .title, url: .url}' 2>/dev/null >> "$TMPFILE" || echo "   ⚠️ Sin datos: $tema" >&2
done
python3 -c "import json; items=[json.loads(l) for l in open('$TMPFILE') if l.strip()]; json.dump(items, open('$OUTPUT','w'), ensure_ascii=False, indent=2); print(len(items))" > /tmp/_prensa_count 2>/dev/null || echo 0 > /tmp/_prensa_count
echo "✅ Buzo de prensa diaria: $(cat /tmp/_prensa_count) noticias"

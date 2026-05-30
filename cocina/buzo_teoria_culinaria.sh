#!/bin/bash
set -euo pipefail
MALETA="$1"; OUTPUT="$2"
SEARXNG_URL="${SEARXNG_URL:-http://178.105.81.83:8888}"
OPENLIBRARY="https://openlibrary.org"
TMPFILE=$(mktemp); trap 'rm -f "$TMPFILE"' EXIT
jq -r '.cocina.teoria[]' "$MALETA" 2>/dev/null | while IFS= read -r tema; do
    [ -z "$tema" ] && continue
    echo "   📚 $tema"
    QUERY=$(python3 -c "import sys,urllib.parse; print(urllib.parse.quote(' '.join(sys.argv[1:])))" $tema 2>/dev/null)
    curl -s --max-time 15 "${OPENLIBRARY}/search.json?q=${QUERY}&limit=5" 2>/dev/null | \
        jq -c --arg tema "$tema" '.docs[]? | {buzo: "teoria", tema: $tema, titulo: .title, autor: (.author_name[0] // "desconocido"), anio: (.first_publish_year // "desconocido"), fuente: "OpenLibrary"}' 2>/dev/null >> "$TMPFILE"
done
python3 -c "import json; items=[json.loads(l) for l in open('$TMPFILE') if l.strip()]; json.dump(items, open('$OUTPUT','w'), ensure_ascii=False, indent=2); print(len(items))" > /tmp/_teoria_count 2>/dev/null || echo 0 > /tmp/_teoria_count
echo "   ✅ $(cat /tmp/_teoria_count) referencias"

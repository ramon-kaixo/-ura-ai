#!/bin/bash
set -euo pipefail
MALETA="$1"
OUTPUT="$2"
ARCHIVO_DIR="$(dirname "$OUTPUT")/../../Archivo"
INDICE="${ARCHIVO_DIR}/indice.json"
SEARXNG_URL="${SEARXNG_URL:-http://178.105.81.83:8888}"
PROXY="http://localhost:3128"
TOPICS=$(jq -r '.practicas.topics[]' "$MALETA" 2>/dev/null || echo "python seguridad clean-code")
HALLAZGOS="["

for topic in $TOPICS; do
    jq -e --arg t "$topic" '.entradas[]? | select(.resumen | test($t;"i"))' "$INDICE" &>/dev/null && echo "   ⏩ $topic ya archivado" && continue
    ARTICULOS=$(curl -s --proxy "$PROXY" --max-time 15 "https://hn.algolia.com/api/v1/search?query=$(echo "$topic" | python3 -c "import sys,urllib.parse; print(urllib.parse.quote(sys.argv[1]))" "$topic" 2>/dev/null)&hitsPerPage=3")
    if ! echo "$ARTICULOS" | jq empty 2>/dev/null; then echo "   ⚠️  JSON inválido: $topic"; continue; fi
    echo "$ARTICULOS" | jq -c '.hits[]?' 2>/dev/null | while read hit; do
        TITLE=$(echo "$hit" | jq -r '.title // ""')
        URL=$(echo "$hit" | jq -r '.url // ""')
        [ -n "$TITLE" ] && HALLAZGOS+="{\"buzo\":\"practicas\",\"titulo\":$(echo "$TITLE" | jq -Rs .),\"url\":$(echo "$URL" | jq -Rs .),\"tema\":\"$topic\"},"
    done

    # Búsqueda adicional con SearXNG
    SEARXNG_QUERY=$(python3 -c "import sys,urllib.parse; print(urllib.parse.quote(sys.argv[1]))" "$topic" 2>/dev/null)
    echo "   🔍 SearXNG: $topic"
    SEARXNG_RESULTS=$(curl -s --max-time 15 "${SEARXNG_URL}/search?q=${SEARXNG_QUERY}&format=json&time_range=month&language=es&safesearch=2" 2>/dev/null) || { echo "   ⚠️  SearXNG no respondió para $topic" >&2; SEARXNG_RESULTS=""; }
    if echo "$SEARXNG_RESULTS" | jq empty 2>/dev/null; then
        echo "$SEARXNG_RESULTS" | jq -c '.results[]? | {titulo: .title, url: .url}' 2>/dev/null | while read hit; do
            TITLE=$(echo "$hit" | jq -r '.title // ""')
            URL=$(echo "$hit" | jq -r '.url // ""')
            if [ -n "$TITLE" ] && [ "$TITLE" != "null" ]; then
                HALLAZGOS+="{\"buzo\":\"practicas\",\"titulo\":$(echo "$TITLE" | jq -Rs .),\"url\":$(echo "$URL" | jq -Rs .),\"tema\":\"$topic\",\"fuente\":\"SearXNG\"},"
            fi
        done
    fi
done
HALLAZGOS="${HALLAZGOS%,}]"
echo "$HALLAZGOS" > "$OUTPUT"
echo "✅ Buzo de prácticas completado"

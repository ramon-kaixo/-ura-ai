#!/bin/bash
set -euo pipefail
# Buzo de Tendencias — Busca proyectos populares via SearXNG
MALETA="$1"
OUTPUT="$2"
SEARXNG_URL="${SEARXNG_URL:-http://178.105.81.83:8888}"
PROXY="http://localhost:3128"
TOPICS=$(jq -r '.tendencias.topics[]' "$MALETA" 2>/dev/null || echo "python javascript ai security devops")
HALLAZGOS="["

for topic in $TOPICS; do
    QUERY=$(python3 -c "import sys,urllib.parse; print(urllib.parse.quote('github trending ' + sys.argv[1]))" "$topic" 2>/dev/null)
    echo "   🔍 SearXNG: $topic"
    RESULTADOS=$(curl -s --max-time 15 "${SEARXNG_URL}/search?q=${QUERY}&format=json&time_range=weekly&language=en&safesearch=2" 2>/dev/null) || { echo "   ⚠️  SearXNG no respondió para $topic" >&2; RESULTADOS=""; }
    if echo "$RESULTADOS" | jq empty 2>/dev/null; then
        echo "$RESULTADOS" | jq -c '.results[]? | {titulo: .title, url: .url}' 2>/dev/null | while read hit; do
            TITLE=$(echo "$hit" | jq -r '.title // "sin título"')
            URL=$(echo "$hit" | jq -r '.url // ""')
            if [ -n "$TITLE" ] && [ "$TITLE" != "null" ]; then
                HALLAZGOS+="{\"buzo\":\"tendencias\",\"titulo\":$(echo "$TITLE" | jq -Rs .),\"url\":$(echo "$URL" | jq -Rs .),\"tema\":\"$topic\",\"fuente\":\"SearXNG\"},"
            fi
        done
    fi
done

HALLAZGOS="${HALLAZGOS%,}]"
echo "$HALLAZGOS" > "$OUTPUT"
echo "✅ Buzo de tendencias completado"

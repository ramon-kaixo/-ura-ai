#!/bin/bash
set -euo pipefail
# Buzo de Video — 7º buzo del Enjambre
# Busca videos semanalmente, puntúa, y marca high-value para descarga automática
MALETA="$1"
OUTPUT="$2"
SEARXNG_URL="${SEARXNG_URL:-http://178.105.81.83:8888}"
TOPICS=$(jq -r '.video.topics[] // .academico.disciplinas[]' "$MALETA" 2>/dev/null || echo "inteligencia artificial python")
THRESHOLD="${VIDEO_THRESHOLD:-50}"
HALLAZGOS="["

for topic in $TOPICS; do
    QUERY=$(python3 -c "import sys,urllib.parse; print(urllib.parse.quote(sys.argv[1]))" "$topic" 2>/dev/null)
    echo "   🎥 $topic"
    RESULTADOS=$(curl -s --max-time 15 "${SEARXNG_URL}/search?q=${QUERY}&format=json&time_range=year&language=es&safesearch=2&engines=youtube,dailymotion" 2>/dev/null) || { echo "⚠️  SearXNG no respondió" >&2; continue; }
    echo "$RESULTADOS" | jq -c '.results[]?' 2>/dev/null | while read item; do
        TITLE=$(echo "$item" | jq -r '.title // ""')
        URL=$(echo "$item" | jq -r '.url // ""')
        DURACION=$(echo "$item" | jq -r '.length // ""')
        [ -z "$TITLE" ] || [ -z "$URL" ] && continue

        # Puntuar
        SCORE=$(echo "$item" | jq --arg q "$topic" '
            (.title | ascii_downcase | split(" ") | map(select(. as $w | $q | ascii_downcase | contains($w))) | length * 10)
            + (if .length and (.length | type == "string") and (.length | test("^[0-9]+:[0-9]+$")) then 5 else 0 end)
        ' 2>/dev/null || echo 0)

        AUTO_DOWNLOAD="false"
        [ "$SCORE" -ge "$THRESHOLD" ] && AUTO_DOWNLOAD="true"

        HALLAZGOS+="{\"buzo\":\"video\",\"titulo\":$(echo "$TITLE" | jq -Rs .),\"url\":$(echo "$URL" | jq -Rs .),\"tema\":\"$topic\",\"score\":$SCORE,\"duracion\":$(echo "$DURACION" | jq -Rs .),\"auto_download\":$AUTO_DOWNLOAD,\"fuente\":\"SearXNG\"},"
    done
done

HALLAZGOS="${HALLAZGOS%,}]"
echo "$HALLAZGOS" > "$OUTPUT"
echo "✅ Buzo de video completado"

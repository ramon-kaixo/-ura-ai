#!/bin/bash
set -euo pipefail
QUERY="$1"
SEARXNG_URL="${SEARXNG_URL:-http://178.105.81.83:8888}"
MAX_VIDEOS="${2:-6}"
OUTPUT="/tmp/ura_videos_$$.json"

echo "🎥 Buscando vídeos para: $QUERY"

VIDEOS=$(curl -s --max-time 15 \
    "${SEARXNG_URL}/search?q=$(python3 -c "import sys,urllib.parse; print(urllib.parse.quote(' '.join(sys.argv[1:])))" "$QUERY receta" 2>/dev/null)&format=json&time_range=year&language=es&safesearch=2&engines=youtube,dailymotion" \
    | jq '[.results[]? | {titulo: .title, url: .url, duracion: .length, fuente: "SearXNG"}]' 2>/dev/null) || { echo "⚠️  SearXNG no respondió" >&2; echo "[]"; exit 1; }

echo "$VIDEOS" | jq --arg q "$QUERY" '
  def score:
    (.titulo | ascii_downcase | split(" ") | map(select(. as $w | $q | ascii_downcase | contains($w))) | length)
    as $matches
    | if .duracion and (.duracion | type == "string") and (.duracion | test("^[0-9]+:[0-9]+$")) then
        ($matches * 10) + 5
      else
        $matches * 10
      end;
  map(. + {score: score}) | sort_by(-.score) | .[0:'"$MAX_VIDEOS"']
' > "$OUTPUT"

echo "📊 Vídeos filtrados: $(jq 'length' "$OUTPUT") candidatos"
echo "$OUTPUT"

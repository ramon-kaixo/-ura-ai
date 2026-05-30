#!/bin/bash
set -euo pipefail
MALETA="$1"; OUTPUT="$2"
SEARXNG_URL="${SEARXNG_URL:-http://178.105.81.83:8888}"
MAX_CITIES="${MAX_CITIES:-52}"
WORKDIR=$(mktemp -d)
trap 'rm -rf "$WORKDIR"' EXIT

# Worker: busca una ciudad, escribe resultado en su propio archivo
worker() {
    local ciudad="$1"
    local out="$WORKDIR/$(echo "$ciudad" | md5 -q 2>/dev/null || echo "$ciudad" | md5sum 2>/dev/null | cut -d' ' -f1 || echo "$ciudad").json"
    local query
    query=$(python3 -c "import sys,urllib.parse; print(urllib.parse.quote('mejores bares restaurantes ' + ' '.join(sys.argv[1:])))" $ciudad 2>/dev/null)
    curl -s --max-time 15 "${SEARXNG_URL}/search?q=${query}&format=json&time_range=year&language=es&safesearch=2" 2>/dev/null | \
        jq -c --arg ciudad "$ciudad" '.results[]? | select(.title != null and .url != null) | {buzo: "bares_espana", ciudad: $ciudad, nombre: .title, url: .url}' 2>/dev/null > "$out"
}
export -f worker
export SEARXNG_URL WORKDIR

echo "   🏙️ Buscando en $MAX_CITIES capitales (8 en paralelo)..."
jq -r '.competencia_espana.capitales[]' "$MALETA" 2>/dev/null | head -n "$MAX_CITIES" | \
    xargs -P 8 -I {} bash -c 'worker "$@"' _ {} 2>&1

# Merge all results
python3 -c "
import json, os
items = []
for f in os.listdir('$WORKDIR'):
    path = os.path.join('$WORKDIR', f)
    if os.path.isfile(path):
        with open(path) as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try: items.append(json.loads(line))
                    except: pass
with open('$OUTPUT', 'w') as f:
    json.dump(items, f, ensure_ascii=False, indent=2)
print(len(items))
" > /tmp/_bares_count 2>/dev/null || echo 0 > /tmp/_bares_count
echo "   ✅ $(cat /tmp/_bares_count) locales en $MAX_CITIES ciudades"

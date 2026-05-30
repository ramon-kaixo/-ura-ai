#!/bin/bash
set -euo pipefail
MALETA="$1"; OUTPUT="$2"
SEARXNG_URL="${SEARXNG_URL:-http://178.105.81.83:8888}"
TMPFILE=$(mktemp); trap 'rm -f "$TMPFILE"' EXIT

# Worker para buscar cada bar/ciudad/evento
worker() {
    local query="$1" label="$2" extra="$3"
    local q
    q=$(python3 -c "import sys,urllib.parse; print(urllib.parse.quote(' '.join(sys.argv[1:])))" $query 2>/dev/null)
    curl -s --max-time 15 "${SEARXNG_URL}/search?q=${q}&format=json&time_range=month&language=es&safesearch=2" 2>/dev/null | \
        jq -c --arg label "$label" --arg extra "$extra" '.results[]? | select(.title != null) | {buzo: "bares_copas", tipo: $label, ref: $extra, titulo: .title, url: .url}' 2>/dev/null
}
export -f worker
export SEARXNG_URL

# 1. Bares de Pamplona — monitorizar competencia
jq -r '.bares_copas.pamplona[]' "$MALETA" 2>/dev/null | while IFS= read -r bar; do
    [ -z "$bar" ] && continue
    echo "   🍸 $bar"
    worker "$bar" "bar_pamplona" "$bar" >> "$TMPFILE" 2>/dev/null
done

# 2. Comparación con otras ciudades (paralelo 4)
jq -r '.bares_copas.ciudades_comparacion[]' "$MALETA" 2>/dev/null | \
    xargs -P 4 -I {} bash -c 'worker "mejores bares copas {} cocteles precios 2026" "ciudad" "{}"' 2>/dev/null >> "$TMPFILE"

# 3. Eventos clave
jq -r '.bares_copas.eventos_clave[]' "$MALETA" 2>/dev/null | while IFS= read -r evento; do
    [ -z "$evento" ] && continue
    echo "   🎉 $evento"
    worker "$evento bares copas Pamplona" "evento" "$evento" >> "$TMPFILE" 2>/dev/null
done

python3 -c "import json; items=[json.loads(l) for l in open('$TMPFILE') if l.strip()]; json.dump(items, open('$OUTPUT','w'), ensure_ascii=False, indent=2); print(len(items))" > /tmp/_copas_count 2>/dev/null || echo 0 > /tmp/_copas_count
echo "✅ Buzo de bares copas: $(cat /tmp/_copas_count) hallazgos"

#!/bin/bash
set -euo pipefail
# buzo_carteles_menu.sh — Descarga y analiza carteles/menus de hosteleria
MALETA="$1"; OUTPUT="$2"
SEARXNG_URL="${SEARXNG_URL:-http://178.105.81.83:8888}"
GX10_URL="${GX10_URL:-http://10.164.1.99:11434/api/chat}"
MODEL="llama3.2-vision:11b"
KNOWLEDGE_DIR="${HOME}/URA/ura_ia_1972/knowledge/diseno"
TMPFILE=$(mktemp); trap 'rm -rf "$TMPFILE"' EXIT

mkdir -p "$KNOWLEDGE_DIR"

jq -r '.video_instagram.ciudades[]' "$MALETA" 2>/dev/null | while IFS= read -r ciudad; do
    [ -z "$ciudad" ] && continue
    for tipo in "cartel bar copas" "menu digital hosteleria" "carta cocteles"; do
        QUERY=$(python3 -c "import sys,urllib.parse; print(urllib.parse.quote(' '.join(sys.argv[1:])))" $tipo $ciudad 2>/dev/null)
        echo "   🖼️ $tipo — $ciudad"
        curl -s --max-time 15 "${SEARXNG_URL}/search?q=${QUERY}&format=json&time_range=year&language=es&safesearch=2" 2>/dev/null | \
            jq -c --arg ciudad "$ciudad" '.results[]? | select(.img_src != null) | {ciudad: $ciudad, titulo: .title, url: .img_src}' 2>/dev/null | while read hit; do
            TITLE=$(echo "$hit" | jq -r '.titulo // ""')
            IMG_URL=$(echo "$hit" | jq -r '.url // ""')
            [ -z "$IMG_URL" ] && continue
            TEMP_IMG=$(mktemp /tmp/ura_cartel_XXXXXX.jpg)
            curl -sL --max-time 10 -o "$TEMP_IMG" "$IMG_URL" 2>/dev/null || { rm -f "$TEMP_IMG"; continue; }
            [ ! -s "$TEMP_IMG" ] && { rm -f "$TEMP_IMG"; continue; }
            PAYLOAD=$(python3 -c "
import json, base64
with open('$TEMP_IMG','rb') as f:
    b64 = base64.b64encode(f.read()).decode()
payload = {
    'model': '$MODEL',
    'messages': [{'role': 'user', 'content': 'Eres un disenador grafico. Extrae UNICAMENTE un JSON con: tipografia, colores_dominantes (3-5 en hex), estructura (vertical/horizontal/mixta), numero_secciones, estilo (minimalista/clasico/moderno/nocturno/elegante).', 'images': [b64]}],
    'stream': False
}
print(json.dumps(payload))
")
            ANALISIS=$(echo "$PAYLOAD" | curl -s --max-time 30 -X POST "$GX10_URL" -H "Content-Type: application/json" -d @- | jq -r '.message.content // "{}"' 2>/dev/null || echo "{}")
            DISENO_ID=$(md5 -qs "$IMG_URL" 2>/dev/null || echo "$IMG_URL" | md5sum 2>/dev/null | cut -d' ' -f1 || echo "$IMG_URL" | python3 -c "import hashlib,sys; print(hashlib.md5(sys.stdin.read().encode()).hexdigest())")
            echo "$ANALISIS" | python3 -c "import json,sys; d=json.load(sys.stdin); d.update({'id':'$DISENO_ID','ciudad':'$ciudad','url':'$IMG_URL'}); json.dump(d, open('${KNOWLEDGE_DIR}/${DISENO_ID}.json','w'), ensure_ascii=False, indent=2)" 2>/dev/null || true
            echo "{\"buzo\":\"carteles_menu\",\"ciudad\":\"$ciudad\",\"diseno_id\":\"$DISENO_ID\",\"url\":\"$IMG_URL\"}" >> "$TMPFILE"
            rm -f "$TEMP_IMG"
        done
    done
done

python3 -c "import json; items=[json.loads(l) for l in open('$TMPFILE') if l.strip()]; json.dump(items, open('$OUTPUT','w'), ensure_ascii=False, indent=2); print(len(items))" > /tmp/_carteles_count 2>/dev/null || echo 0 > /tmp/_carteles_count
echo "✅ Buzo carteles/menus: $(cat /tmp/_carteles_count) disenos"

#!/bin/bash
set -euo pipefail
MALETA="$1"; OUTPUT="$2"
SEARXNG_URL="${SEARXNG_URL:-http://178.105.81.83:8888}"
GX10_URL="${GX10_URL:-http://10.164.1.99:11434/api/chat}"
MODEL="${OLLAMA_MODEL:-qwen3:32b}"
WORKDIR=$(mktemp -d); trap 'rm -rf "$WORKDIR"' EXIT
OLLAMA_HOST="${OLLAMA_HOST:-http://10.164.1.99:11434}"

# Detectar mejor modelo disponible en el GX10
echo "   🔍 Detectando modelos en GX10..."
MODELS=$(curl -s --max-time 5 "${OLLAMA_HOST}/api/tags" 2>/dev/null | jq -r '.models[].name' 2>/dev/null || echo "")
VISION_MODEL=""
for candidate in "llama3.2-vision:11b" "llama3.2-vision" "qwen2-vl:7b" "qwen2.5-vl:7b" "bakllava" "llava:7b" "llava:13b"; do
    if echo "$MODELS" | grep -qi "$candidate"; then
        VISION_MODEL=$(echo "$MODELS" | grep -i "$candidate" | head -1)
        break
    fi
done

if [ -n "$VISION_MODEL" ]; then
    MODEL="$VISION_MODEL"
    VISION=true
    echo "   🧠 Modelo visual: $MODEL"
else
    MODEL="qwen3:32b"
    VISION=false
    echo "   ⚠️  Sin modelo visual. Analisis textual: $MODEL"
fi

jq -r '.video_instagram.ciudades[]' "$MALETA" 2>/dev/null | while IFS= read -r ciudad; do
    [ -z "$ciudad" ] && continue
    jq -r '.video_instagram.tipos_local[]' "$MALETA" 2>/dev/null | while IFS= read -r tipo; do
        [ -z "$tipo" ] && continue
        QUERY=$(python3 -c "import sys,urllib.parse; print(urllib.parse.quote('instagram reels ' + ' '.join(sys.argv[1:])))" $tipo $ciudad 2>/dev/null)
        echo "   🎥 $tipo en $ciudad"
        curl -s --max-time 15 "${SEARXNG_URL}/search?q=${QUERY}&format=json&time_range=year&language=es&safesearch=2" 2>/dev/null | \
            jq -c '.results[]? | select(.title != null and .url != null) | {titulo: .title, url: .url}' 2>/dev/null | while read hit; do
            TITLE=$(echo "$hit" | jq -r '.titulo // ""'); URL=$(echo "$hit" | jq -r '.url // ""')
            [ -z "$URL" ] && continue
            VIDEO="$WORKDIR/$(date +%s)_$$.mp4"
            echo "      📥 $TITLE"
            yt-dlp --max-duration 30 --no-audio -o "$VIDEO" "$URL" 2>/dev/null || { rm -f "$VIDEO"; continue; }
            [ ! -f "$VIDEO" ] && continue
            FRAME="$WORKDIR/frame_$$.jpg"
            ffmpeg -i "$VIDEO" -vframes 1 -q:v 2 "$FRAME" 2>/dev/null || { rm -f "$VIDEO" "$FRAME"; continue; }
            # Enviar frame a GX10 para análisis visual o textual
            PROMPT="Eres un critico de diseno para hosteleria. Analiza $([ "$VISION" = true ] && echo "la imagen de" || echo "las tendencias de diseno de") un local de $tipo en $ciudad. Responde solo APROBADO o DESCARTADO."
            PAYLOAD=$(python3 -c "
import json, base64
payload = {
    'model': '$MODEL',
    'messages': [{'role': 'user', 'content': '$PROMPT'}],
    'stream': False
}
if '$VISION' == 'true':
    with open('$FRAME','rb') as f:
        payload['messages'][0]['images'] = [base64.b64encode(f.read()).decode()]
print(json.dumps(payload))
")
            RESPUESTA=$(echo "$PAYLOAD" | curl -s --max-time 30 -X POST "$GX10_URL" \
                -H "Content-Type: application/json" -d @- | jq -r '.message.content' 2>/dev/null || echo "DESCARTADO")
            if echo "$RESPUESTA" | grep -qi "APROBADO"; then
                mkdir -p "${HOME}/knowledge/media"
                FINAL="${HOME}/knowledge/media/hosteleria_${ciudad}_$(date +%s).mp4"
                cp "$VIDEO" "$FINAL"
                jq -c -n --arg ciudad "$ciudad" --arg tipo "$tipo" --arg titulo "$TITLE" --arg url "$URL" --arg archivo "$FINAL" '{buzo: "video_instagram", ciudad: $ciudad, tipo: $tipo, titulo: $titulo, url: $url, archivo: $archivo, estado: "aprobado"}' >> "$WORKDIR/resultados.jsonl"
                echo "         ✅ Aprobado"
            else
                echo "         🗑️  Descartado"
            fi
            rm -f "$VIDEO" "$FRAME"
        done
    done
done

python3 -c "import json; items=[json.loads(l) for l in open('$WORKDIR/resultados.jsonl') if l.strip()]; json.dump(items, open('$OUTPUT','w'), ensure_ascii=False, indent=2); print(len(items))" > /tmp/_ig_count 2>/dev/null || echo 0 > /tmp/_ig_count
echo "✅ Buzo video_instagram: $(cat /tmp/_ig_count) aprobados"

#!/bin/bash
set -euo pipefail
# analizar_periodo.sh — Analisis enriquecido con multiples fotogramas
CAMARA="$1"
INICIO="$2"
FIN="$3"
FRIGATE_URL="${FRIGATE_URL:-http://10.164.1.99:5000}"
GX10_URL="http://10.164.1.99:11434/api/chat"
MODEL="llama3.2-vision:11b"
OUTPUT_DIR="${HOME}/URA/ura_ia_1972/knowledge/analisis_periodos"
mkdir -p "$OUTPUT_DIR"

echo "🎥 $CAMARA de $INICIO a $FIN (secuencia)"

EVENTOS=$(curl -s "${FRIGATE_URL}/api/events?camera=${CAMARA}&after=${INICIO}&before=${FIN}&label=person" 2>/dev/null | jq -c '.[]' 2>/dev/null || echo "")
[ -z "$EVENTOS" ] && echo "   Sin eventos" && echo '[]' > "${OUTPUT_DIR}/analisis_${CAMARA}_$(date +%Y%m%d_%H%M%S).json" && exit 0

TMPFILE=$(mktemp); trap 'rm -rf "$TMPFILE"' EXIT

echo "$EVENTOS" | while read -r evento; do
    [ -z "$evento" ] && continue
    EVENT_ID=$(echo "$evento" | jq -r '.id // ""') || continue
    START=$(echo "$evento" | jq -r '.start_time // ""')
    END=$(echo "$evento" | jq -r '.end_time // ""')

    TEMP_CLIP=$(mktemp /tmp/ura_clip_XXXXXX.mp4)
    curl -s -o "$TEMP_CLIP" "${FRIGATE_URL}/api/events/${EVENT_ID}/clip.mp4" 2>/dev/null || { rm -f "$TEMP_CLIP"; continue; }
    [ ! -s "$TEMP_CLIP" ] && { rm -f "$TEMP_CLIP"; continue; }

    # Extraer 1 frame/segundo (max 5 frames) para analisis de secuencia
    FRAMES_DIR=$(mktemp -d /tmp/ura_frames_XXXXXX)
    ffmpeg -i "$TEMP_CLIP" -vf "fps=1" -vframes 5 "${FRAMES_DIR}/f_%02d.jpg" 2>/dev/null || { rm -rf "$TEMP_CLIP" "$FRAMES_DIR"; continue; }

    # Enviar multiples frames al modelo visual
    PAYLOAD=$(python3 -c "
import json, base64, os
images = []
for f in sorted(os.listdir('$FRAMES_DIR')):
    fp = os.path.join('$FRAMES_DIR', f)
    if os.path.isfile(fp):
        with open(fp,'rb') as fh:
            images.append(base64.b64encode(fh.read()).decode())
payload = {
    'model': '$MODEL',
    'messages': [{'role': 'user', 'content': 'Eres un analista de videovigilancia. Estos fotogramas son de un mismo evento. Describe la secuencia: que hace la persona? Hay algo inusual? Es empleado o cliente? Se conciso.', 'images': images}],
    'stream': False
}
print(json.dumps(payload))
")
    ANALISIS=$(echo "$PAYLOAD" | curl -s --max-time 60 -X POST "$GX10_URL" -H "Content-Type: application/json" -d @- | jq -r '.message.content // "sin analisis"' 2>/dev/null || echo "sin analisis")

    jq -c -n --arg id "$EVENT_ID" --arg inicio "$START" --arg fin "$END" --arg analisis "$ANALISIS" '{evento_id: $id, inicio: $inicio, fin: $fin, analisis_secuencia: $analisis}' >> "$TMPFILE"
    rm -rf "$TEMP_CLIP" "$FRAMES_DIR"
done

python3 -c "import json; items=[json.loads(l) for l in open('$TMPFILE') if l.strip()]; json.dump(items, open('${OUTPUT_DIR}/analisis_${CAMARA}_$(date +%Y%m%d_%H%M%S).json','w'), ensure_ascii=False, indent=2); print(len(items))" > /tmp/_analisis_count 2>/dev/null || echo 0 > /tmp/_analisis_count
echo "✅ $(cat /tmp/_analisis_count) eventos (secuencia)"

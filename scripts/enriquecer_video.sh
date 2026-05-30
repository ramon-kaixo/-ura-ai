#!/bin/bash
set -euo pipefail
# enriquecer_video.sh — Genera metadatos enriquecidos para un video
VIDEO_FILE="$1"
GX10_URL="${GX10_URL:-http://10.164.1.99:11434/api/chat}"
MODEL="$2"
OUTPUT_DIR="${HOME}/URA/ura_ia_1972/knowledge/metadata"
mkdir -p "$OUTPUT_DIR"

VIDEO_ID=$(basename "$VIDEO_FILE" .mp4)
FRAMES_DIR="/tmp/ura_frames_${VIDEO_ID}"
mkdir -p "$FRAMES_DIR"

echo "   🎞️ Extrayendo frames (1 cada 5s)..."
ffmpeg -i "$VIDEO_FILE" -vf "fps=1/5" "${FRAMES_DIR}/frame_%03d.jpg" 2>/dev/null

echo "   🧠 Analizando frames con GX10..."
ANALISIS="["
for frame in "${FRAMES_DIR}"/*.jpg; do
    [ ! -f "$frame" ] && continue
    FRAME_B64=$(base64 < "$frame" | tr -d '\n')
    PAYLOAD=$(python3 -c "
import json, base64
with open('$frame','rb') as f:
    b64 = base64.b64encode(f.read()).decode()
payload = {
    'model': '$MODEL',
    'messages': [{'role': 'user', 'content': 'Describe brevemente esta escena de hosteleria: iluminacion, colores, tipo de plano, elementos destacados.', 'images': [b64]}],
    'stream': False
}
print(json.dumps(payload))
")
    RESPUESTA=$(echo "$PAYLOAD" | curl -s --max-time 30 -X POST "$GX10_URL" -H "Content-Type: application/json" -d @- | jq -r '.message.content // "sin analisis"' 2>/dev/null || echo "sin analisis")
    TIMESTAMP=$(basename "$frame" .jpg | sed 's/frame_//')
    SEGUNDO=$((10#$TIMESTAMP * 5))
    ANALISIS+="{\"segundo\":$SEGUNDO,\"descripcion\":$(echo "$RESPUESTA" | jq -Rs .)},"
done
ANALISIS="${ANALISIS%,}]"

python3 -c "
import json
with open('$VIDEO_FILE','rb') as f:
    import subprocess
    dur = subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0','$VIDEO_FILE'], capture_output=True, text=True, timeout=30).stdout.strip()
    duracion = float(dur) if dur else 0
with open('${OUTPUT_DIR}/${VIDEO_ID}.json','w') as f:
    json.dump({
        'video_id': '$VIDEO_ID',
        'fecha_analisis': '$('"$(date -u +%Y-%m-%dT%H:%M:%SZ)"')',
        'duracion_segundos': duracion,
        'escenas': json.loads('''$ANALISIS'''),
        'puntuacion_calidad': len(json.loads('''$ANALISIS'''))
    }, f, ensure_ascii=False, indent=2)
"

rm -rf "$FRAMES_DIR"
echo "   ✅ Metadatos: ${OUTPUT_DIR}/${VIDEO_ID}.json"

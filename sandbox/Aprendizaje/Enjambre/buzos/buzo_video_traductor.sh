#!/bin/bash
set -euo pipefail
VIDEO_URL="$1"
TARGET_LANG="${2:-es}"
OUTPUT_DIR="${HOME}/URA/ura_ia_1972/knowledge/media"
mkdir -p "$OUTPUT_DIR"

echo "⬇️  Descargando vídeo: $VIDEO_URL"

VIDEO_FILE=$(yt-dlp --print filename -o "${OUTPUT_DIR}/%(title)s.%(ext)s" "$VIDEO_URL" 2>/dev/null)
yt-dlp -o "${OUTPUT_DIR}/%(title)s.%(ext)s" "$VIDEO_URL" 2>&1 | tail -3

if [ ! -f "$VIDEO_FILE" ]; then
    VIDEO_FILE=$(ls -t "${OUTPUT_DIR}"/*.mp4 2>/dev/null | head -1)
fi

if [ -z "$VIDEO_FILE" ] || [ ! -f "$VIDEO_FILE" ]; then
    echo "❌ No se pudo descargar el vídeo"
    exit 1
fi

echo "📁 Vídeo descargado: $VIDEO_FILE"

echo "🔍 Detectando idioma original..."
ORIG_LANG=$(python3 -c "
import subprocess, json
result = subprocess.run(['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_streams', '$VIDEO_FILE'], capture_output=True, text=True)
data = json.loads(result.stdout)
for stream in data.get('streams', []):
    if stream.get('codec_type') == 'audio':
        lang = stream.get('tags', {}).get('language', 'unknown')
        print(lang)
        break
" 2>/dev/null || echo "unknown")
echo "   Idioma original: $ORIG_LANG"

if [ "$ORIG_LANG" != "spa" ] && [ "$ORIG_LANG" != "es" ] && [ "$ORIG_LANG" != "unknown" ]; then
    echo "🌐 Extrayendo audio para transcripción..."
    AUDIO_FILE="${VIDEO_FILE%.*}.wav"
    ffmpeg -y -i "$VIDEO_FILE" -vn -acodec pcm_s16le -ar 16000 -ac 1 "$AUDIO_FILE" 2>/dev/null
    echo "   Audio extraído: $AUDIO_FILE"
    echo "⚠️  Traducción automática no disponible (pyvideotrans no existe como paquete)"
    echo "   El audio está en $AUDIO_FILE para procesamiento manual"
else
    echo "✅ El vídeo ya está en español o no se pudo detectar el idioma"
fi

echo "✅ Procesamiento completado: $VIDEO_FILE"

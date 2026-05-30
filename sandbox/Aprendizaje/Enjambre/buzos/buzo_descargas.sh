#!/bin/bash
set -euo pipefail
MALETA="$1"
OUTPUT="$2"
ARCHIVO_DIR="$(dirname "$OUTPUT")/../../Archivo"
INDICE="${ARCHIVO_DIR}/indice.json"
PROXY="http://localhost:3128"
OLLAMA_URL="${OLLAMA_URL:-http://10.164.1.99:11434/api/chat}"
MODEL="${OLLAMA_MODEL:-qwen3:32b}"
mkdir -p "${ARCHIVO_DIR}/documentos" "${ARCHIVO_DIR}/resumenes"

if command -v lynx &>/dev/null; then
    HTML_TO_TEXT="lynx -dump -stdin"
else
    HTML_TO_TEXT="python3 -c \"import sys; from html.parser import HTMLParser; import html; print(html.unescape(sys.stdin.read()))\""
fi

INFORMES_DIR="$(dirname "$OUTPUT")/../informes"
URLS=$(jq -r '.[] | select(.url) | .url' "$INFORMES_DIR"/hallazgos_*.json 2>/dev/null | sort -u)

for url in $URLS; do
    jq -e --arg u "$url" '.entradas[]? | select(.url == $u)' "$INDICE" &>/dev/null && echo "   ⏩ Ya archivado: $url" && continue
    CONTENIDO=$(curl -sL --proxy "$PROXY" --max-time 30 "$url" 2>/dev/null | eval "$HTML_TO_TEXT" 2>/dev/null | head -c 5000)
    [ -z "$CONTENIDO" ] && continue
    DOC_ID=$(echo "$url" | md5 -q 2>/dev/null || echo "$url" | md5sum 2>/dev/null | cut -d' ' -f1 || echo "doc_$(date +%s)")
    CAT="general"
    for kw in python ia seguridad herramienta; do echo "$CONTENIDO" | grep -qi "$kw" && CAT="$kw" && break; done
    mkdir -p "${ARCHIVO_DIR}/documentos/${CAT}"
    echo "$CONTENIDO" > "${ARCHIVO_DIR}/documentos/${CAT}/${DOC_ID}.txt"
    RESUMEN=$(curl -s --max-time 30 -X POST "$OLLAMA_URL" -H "Content-Type: application/json" \
        -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"Resume en 3 oraciones:\n$CONTENIDO\"}],\"stream\":false}" | \
        jq -r '.message.content' 2>/dev/null || echo "Sin resumen")
    echo "$RESUMEN" > "${ARCHIVO_DIR}/resumenes/${DOC_ID}.md"
    python3 -c "
import json
with open('$INDICE') as f: idx = json.load(f)
idx['entradas'].append({'url':'$url','categoria':'$CAT','fecha':'$(date -u +%Y-%m-%dT%H:%M:%SZ)','archivo':'documentos/${CAT}/${DOC_ID}.txt'})
with open('$INDICE','w') as f: json.dump(idx, f, indent=2)" 2>/dev/null
    echo "   📥 $url → $CAT"
done
echo '[]' > "$OUTPUT"
python3 "${HOME}/URA/ura_ia_1972/sandbox/Aprendizaje/Archivo/semantic_chunker.py" 2>/dev/null || true
echo "✅ Buzo de descargas completado"

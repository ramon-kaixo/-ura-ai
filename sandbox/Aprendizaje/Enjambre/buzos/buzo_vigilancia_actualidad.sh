#!/bin/bash
set -euo pipefail
# buzo_vigilancia_actualidad.sh — Novedades quincenales en videovigilancia
MALETA="$1"; OUTPUT="$2"
SEARXNG_URL="${SEARXNG_URL:-http://178.105.81.83:8888}"
TMPFILE=$(mktemp); trap 'rm -f "$TMPFILE"' EXIT

echo "   🔍 Novedades videovigilancia..."

# Temas de busqueda (bash 3.2 compatible)
for entrada in \
  "tendencias|videovigilancia IP tendencias 2026 camaras inteligencia artificial" \
  "vulnerabilidades|camaras IP vulnerabilidades CVE 2026 seguridad" \
  "modelos_ia|modelos IA analisis video open source 2026 edge AI" \
  "frigate|Frigate NVR novedades 2026 deteccion objetos" \
  "normativa|normativa videovigilancia Espana 2026 LOPDGDD RGPD"; do
    categoria="${entrada%%|*}"
    query="${entrada#*|}"
    QUERY=$(python3 -c "import sys,urllib.parse; print(urllib.parse.quote(' '.join(sys.argv[1:])))" $query 2>/dev/null)
    curl -s --max-time 15 "${SEARXNG_URL}/search?q=${QUERY}&format=json&time_range=month&language=es&safesearch=2" 2>/dev/null | \
        jq -c --arg cat "$categoria" '.results[]? | {buzo: "vigilancia_actualidad", categoria: $cat, titulo: .title, url: .url}' 2>/dev/null >> "$TMPFILE" || true
done

python3 -c "import json; items=[json.loads(l) for l in open('$TMPFILE') if l.strip()]; json.dump(items, open('$OUTPUT','w'), ensure_ascii=False, indent=2); print(len(items))" > /tmp/_vig_act_count 2>/dev/null || echo 0 > /tmp/_vig_act_count
echo "   ✅ $(cat /tmp/_vig_act_count) hallazgos"

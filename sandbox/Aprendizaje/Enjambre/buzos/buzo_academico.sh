#!/bin/bash
set -euo pipefail
MALETA="$1"
OUTPUT="$2"
ARCHIVO_DIR="$(dirname "$OUTPUT")/../../Archivo"
INDICE="${ARCHIVO_DIR}/indice.json"
SEARXNG_URL="${SEARXNG_URL:-http://178.105.81.83:8888}"
PROXY="http://localhost:3128"

DISCIPLINAS=$(jq -r '.academico.disciplinas[]' "$MALETA" 2>/dev/null)
PAISES=$(jq -r '.academico.paises[]' "$MALETA" 2>/dev/null)
FUENTES=$(jq -r '.academico.fuentes | to_entries[] | "\(.key)||\(.value)"' "$MALETA" 2>/dev/null)

mkdir -p "$(dirname "$INDICE")"
[ -f "$INDICE" ] || echo '{"entradas":[]}' > "$INDICE"

HALLAZGOS="["

for disciplina in $DISCIPLINAS; do
    for pais in $PAISES; do
        QUERY="${disciplina} ${pais}"

        # Anti-bucle: omitir si ya se buscó en los últimos 30 días
        if jq -e --arg q "$QUERY" '.entradas[]? | select(.query == $q and ((now - (.fecha | strptime("%Y-%m-%d") | mktime)) / 86400 | floor) < 30)' "$INDICE" &>/dev/null; then
            echo "   ⏩ Ya buscado recientemente: $QUERY"
            continue
        fi

        while IFS='||' read -r nombre url_template; do
            url=$(echo "$url_template" | sed "s|http://localhost:8888|$SEARXNG_URL|" | sed "s|{}|$(echo "$QUERY" | python3 -c "import sys,urllib.parse; print(urllib.parse.quote(sys.argv[1]))" "$QUERY" 2>/dev/null)|")
            [ "$nombre" = "searxng" ] && echo "   🔍 SearXNG: $disciplina $pais"
            RESULTADOS=$(curl -s --max-time 15 "$url" 2>/dev/null) || { echo "   ⚠️  $nombre no respondió para $disciplina $pais" >&2; RESULTADOS=""; }
        # Fuentes experimentales (Dialnet, Redalyc - pueden no tener API pública)
        if [ "$nombre" = "dialnet" ] || [ "$nombre" = "redalyc" ]; then
            echo "   ⚠️  Fuente experimental: $nombre"
            [ -z "$RESULTADOS" ] && continue
        fi


            if [ "$nombre" = "semantic_scholar" ]; then
                echo "$RESULTADOS" | python3 -c "
import sys,json
try:
    for p in json.load(sys.stdin).get('data',[]):
        print(json.dumps({'titulo':p.get('title',''),'url':p.get('url',''),'fuente':'Semantic Scholar'}))
except: pass" 2>/dev/null | while read item; do
                    HALLAZGOS+="{\"buzo\":\"academico\",\"disciplina\":\"$disciplina\",\"pais\":\"$pais\",$(echo "$item" | python3 -c "import sys,json; d=json.loads(sys.argv[1]); print(f'\"titulo\":{json.dumps(d[\"titulo\"])},\"url\":{json.dumps(d[\"url\"])},\"fuente\":{json.dumps(d[\"fuente\"])}')" "$item" 2>/dev/null)},"
                done
            elif [ "$nombre" = "arxiv" ]; then
                echo "$RESULTADOS" | python3 -c "
import sys,json,xml.etree.ElementTree as ET
try:
    root=ET.fromstring(sys.stdin.read())
    ns={'atom':'http://www.w3.org/2005/Atom'}
    for e in root.findall('atom:entry',ns):
        print(json.dumps({'titulo':e.find('atom:title',ns).text,'url':e.find('atom:id',ns).text,'fuente':'arXiv'}))
except: pass" 2>/dev/null | while read item; do
                    HALLAZGOS+="{\"buzo\":\"academico\",\"disciplina\":\"$disciplina\",\"pais\":\"$pais\",$(echo "$item" | python3 -c "import sys,json; d=json.loads(sys.argv[1]); print(f'\"titulo\":{json.dumps(d[\"titulo\"])},\"url\":{json.dumps(d[\"url\"])},\"fuente\":{json.dumps(d[\"fuente\"])}')" "$item" 2>/dev/null)},"
                done
            elif [ "$nombre" = "searxng" ]; then
                echo "$RESULTADOS" | jq -c '.results[]? | {titulo: .title, url: .url}' 2>/dev/null | while read item; do
                    TITLE=$(echo "$item" | jq -r '.titulo // "sin título"')
                    URL=$(echo "$item" | jq -r '.url // ""')
                    HALLAZGOS+="{\"buzo\":\"academico\",\"disciplina\":\"$disciplina\",\"pais\":\"$pais\",$(echo "$item" | python3 -c "import sys,json; d=json.loads(sys.argv[1]); print(f'\"titulo\":{json.dumps(d[\"titulo\"])},\"url\":{json.dumps(d[\"url\"])}')" "$item" 2>/dev/null),\"fuente\":\"SearXNG\"},"
                done
            fi
        done <<< "$FUENTES"

        # Registrar búsqueda en el índice (anti-bucle)
        python3 -c "
import json
with open('$INDICE') as f: idx = json.load(f)
idx.setdefault('entradas',[])
# Eliminar entrada anterior del mismo query si existe
idx['entradas'] = [e for e in idx['entradas'] if e.get('query') != '$QUERY']
idx['entradas'].append({'query':'$QUERY','fecha':'$(date +%Y-%m-%d)','disciplina':'$disciplina','pais':'$pais'})
with open('$INDICE','w') as f: json.dump(idx, f, indent=2)
" 2>/dev/null
    done
done
HALLAZGOS="${HALLAZGOS%,}]"
echo "$HALLAZGOS" > "$OUTPUT"
echo "✅ Buzo académico completado"

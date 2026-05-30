#!/bin/bash
set -euo pipefail
MALETA="$1"
OUTPUT="$2"
ARCHIVO_DIR="$(dirname "$OUTPUT")/../../Archivo"
CATALOGO="${ARCHIVO_DIR}/modelos/catalogo.json"
OLLAMA_GX10="http://10.164.1.99:11434"
OLLAMA_MAC="http://localhost:11434"

mkdir -p "$(dirname "$CATALOGO")"
HALLAZGOS="["

echo "📊 Inventariando modelos..."
for endpoint in "$OLLAMA_GX10" "$OLLAMA_MAC"; do
    MODELOS=$(curl -s "$endpoint/api/tags" 2>/dev/null | python3 -c "
import sys,json
try:
    d=json.load(sys.stdin)
    for m in d.get('models',[]):
        print(f\"{m['name']} {m.get('size',0)}\")
except: pass
" 2>/dev/null)
    if [ -n "$MODELOS" ]; then
        while IFS= read -r modelo || [ -n "$modelo" ]; do
            nombre=$(echo "$modelo" | awk '{print $1}')
            tamano=$(echo "$modelo" | awk '{print $2}')
            HALLAZGOS+="{\"buzo\":\"modelos\",\"accion\":\"inventariado\",\"modelo\":\"$nombre\",\"tamano\":\"$tamano\",\"ubicacion\":\"$endpoint\"},"
        done <<< "$MODELOS"
    fi
done

echo "🔍 Buscando modelos candidatos..."
for esp in code security python documentation analysis; do
    CANDIDATOS=$(curl -s "https://ollama.com/api/search?q=${esp}&type=model" 2>/dev/null | python3 -c "
import sys,json
try:
    d=json.load(sys.stdin)
    for m in d.get('models',[])[:3]:
        print(json.dumps({'nombre':m.get('name','?'),'desc':m.get('description','')}))
except: pass
" 2>/dev/null)
    if [ -n "$CANDIDATOS" ]; then
        echo "$CANDIDATOS" | while read c; do
            nombre=$(echo "$c" | python3 -c "import sys,json; print(json.load(sys.stdin)['nombre'])")
            desc=$(echo "$c" | python3 -c "import sys,json; print(json.load(sys.stdin)['desc'][:80])")
            HALLAZGOS+="{\"buzo\":\"modelos\",\"accion\":\"candidato\",\"modelo\":\"$nombre\",\"especialidad\":\"$esp\",\"descripcion\":\"$desc\"},"
        done
    fi
done
HALLAZGOS="${HALLAZGOS%,}]"
echo "$HALLAZGOS" > "$OUTPUT"
echo "✅ Buzo de modelos finalizado"

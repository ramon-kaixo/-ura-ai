#!/bin/bash
# crawler_alemania.sh — Recolección de documentación técnica en Alemania
# Uso: bash crawler_alemania.sh [target_dir]
# Ejecutar EN el servidor de Alemania (Hetzner)

TARGET="${1:-/data/recoleccion_tecnica}"
mkdir -p "$TARGET"
cd "$TARGET" || exit 1

echo "=== CRAWLER ALEMANIA ==="
echo "Target: $TARGET"
echo "Inicio: $(date)"

# Temas de búsqueda (documentación técnica)
TOPICS=(
  "Enterprise Agentic System Architecture PDF"
  "Role Based Access Control for LLM Agents"
  "Dynamic UI generation for AI Agents schema"
  "Multi-tenant Agent Orchestration architecture"
  "LangChain multi-agent RBAC 2025 2026"
  "LlamaIndex agent workflow isolation"
  "Dify platform RBAC multi-tenant design"
  "Microsoft AutoGen agent hierarchy permissions"
)

RESULTS=0
TOTAL_SIZE=0

for topic in "${TOPICS[@]}"; do
  echo ""
  echo "--- Buscando: $topic ---"
  
  # DDG Lite search (no API key needed, works everywhere)
  SEARCH_URL="https://lite.duckduckgo.com/lite"
  RESULTS_HTML=$(curl -s -X POST "$SEARCH_URL" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -H "User-Agent: Mozilla/5.0 (compatible; URA/1.0)" \
    -d "q=$(echo "$topic" | python3 -c 'import sys,urllib.parse; print(urllib.parse.quote(sys.stdin.read()))')" \
    2>/dev/null)
  
  # Extract links
  LINKS=$(echo "$RESULTS_HTML" | grep -oP 'href="(https?://[^"]+)"' | cut -d'"' -f2 | head -5)
  
  for url in $LINKS; do
    echo "  Downloading: $url"
    DOMAIN=$(echo "$url" | awk -F/ '{print $3}' | tr '.' '_')
    FILENAME="${DOMAIN}_$(date +%s)_$(echo "$url" | md5sum | cut -c1-8)"
    
    # Download with timeout
    curl -s -L --max-time 30 -o "${FILENAME}.html" "$url" 2>/dev/null
    if [ -f "${FILENAME}.html" ] && [ -s "${FILENAME}.html" ]; then
      SIZE=$(stat -c%s "${FILENAME}.html" 2>/dev/null || echo 0)
      TOTAL_SIZE=$((TOTAL_SIZE + SIZE))
      RESULTS=$((RESULTS + 1))
      echo "    → ${FILENAME}.html ($SIZE bytes)"
    else
      rm -f "${FILENAME}.html"
    fi
    sleep 2  # rate limit
  done
done

echo ""
echo "=== RECOLECCIÓN COMPLETADA ==="
echo "Archivos descargados: $RESULTS"
echo "Tamaño total: $TOTAL_SIZE bytes ($((TOTAL_SIZE / 1024)) KB)"
echo "Directorio: $TARGET"
echo "Fin: $(date)"

# Señal de finalización
echo "RECOLECCION_COMPLETADA" > "$TARGET/.done"

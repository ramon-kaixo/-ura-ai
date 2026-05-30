#!/bin/bash
set -euo pipefail
REPO="${HOME}/URA/ura_ia_1972"
INFORMES_DIR="${REPO}/sandbox/Aprendizaje/Enjambre/informes"
OUTPUT_DIR="${REPO}/docs/marketing"
mkdir -p "$OUTPUT_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
GX10_URL="${GX10_URL:-http://10.164.1.99:11434/api/chat}"
MODEL="${OLLAMA_MODEL:-qwen3:32b}"

EVENTOS=$(cat "${INFORMES_DIR}"/hallazgos_prensa_*.json 2>/dev/null | jq -s 'add' 2>/dev/null || echo "[]")
COMPETENCIA=$(cat "${INFORMES_DIR}"/hallazgos_bares_*.json 2>/dev/null | jq -s 'add' 2>/dev/null || echo "[]")

if [ "$EVENTOS" = "[]" ] && [ "$COMPETENCIA" = "[]" ]; then
    echo "❌ No hay datos de prensa ni competencia"
    exit 1
fi

PROMPT=$(python3 -c "
import json
eventos = json.loads('''$EVENTOS''')
competencia = json.loads('''$COMPETENCIA''')
texto = 'Eres un experto en marketing gastronomico. Genera UNICAMENTE un JSON con: campana_semanal, contenido_redes (3-5 posts), promocion_especial, newsletter_tema.\n\n'
texto += 'EVENTOS:\n' + json.dumps(eventos[:5], ensure_ascii=False) + '\n\n'
texto += 'COMPETENCIA:\n' + json.dumps(competencia[:5], ensure_ascii=False)
print(json.dumps(texto))
")

curl -s --max-time 90 -X POST "$GX10_URL" \
    -H "Content-Type: application/json" \
    -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":$PROMPT}],\"stream\":false}" | \
    jq -r '.message.content // "Error"' 2>/dev/null > "${OUTPUT_DIR}/marketing_${TIMESTAMP}.json"

echo "✅ Marketing guardado en marketing_${TIMESTAMP}.json"

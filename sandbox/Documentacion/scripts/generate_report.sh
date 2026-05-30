#!/bin/bash
REGISTRY_URL="http://127.0.0.1:5100/agents"
OUTPUT_DIR="${HOME}/URA/ura_ia_1972/docs/informes"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
mkdir -p "$OUTPUT_DIR"
echo "# Informe del Sistema URA — $(date)" > "$OUTPUT_DIR/informe_${TIMESTAMP}.md"
echo "" >> "$OUTPUT_DIR/informe_${TIMESTAMP}.md"
curl -s "$REGISTRY_URL" | python3 -c "
import json, sys
agents = json.load(sys.stdin)
print(f'## Agentes registrados: {len(agents)}')
print()
for a in agents:
    print(f\"- **{a['id']}** ({a.get('type','?')}) — IP: {a.get('ip','?')} — Puerto: {a.get('port','?')} — Latido: {a.get('last_seen','?')}\")
" >> "$OUTPUT_DIR/informe_${TIMESTAMP}.md"
echo "✅ Informe: $OUTPUT_DIR/informe_${TIMESTAMP}.md"

#!/bin/bash
# Auditoría multi-modelo v2 — usa llama.cpp router (puerto 8288)
set -euo pipefail

PROJECT="$HOME/URA/ura_ia_1972"
OUTDIR="$HOME/logs/auditoria_multimodelo"
mkdir -p "$OUTDIR"
API="http://localhost:8288/v1/chat/completions"

FILES=(
  "core/agente_documentador.py"
  "core/auto_healing.py"
  "core/autonomous_agent.py"
  "core/autonomous_maintenance.py"
  "core/backup_system.py"
  "core/buscadores/buscador_documentacion.py"
  "core/code_agents/generators/generator_parser.py"
  "core/code_agents/mobile/agente_registrador.py"
  "core/code_agents/orchestrator_mobile.py"
  "core/code_agents/tools/install_tools.py"
  "core/code_assistant.py"
  "core/consciousness_orchestrator.py"
  "core/conversation_truncator.py"
  "core/disk_cleaner.py"
  "core/disk_monitor.py"
  "core/health_monitor.py"
  "core/healthcheck.py"
  "core/lector_documentacion.py"
  "core/maintenance_cycle.py"
  "core/query_decomposer.py"
  "core/sandbox.py"
  "core/sandbox_orchestrator.py"
  "core/search_cache.py"
  "core/secure_trash.py"
  "core/security/hermetic_states.py"
  "core/system_prompt.py"
  "core/toshiba_backup.py"
  "core/ura_anticipation.py"
)

PROMPT="Eres un revisor de codigo senior Python. Analiza este archivo y reporta SOLO bugs reales que romperian en produccion. Para cada bug: NUMERO DE LINEA | QUE FALLA | COMO ARREGLARLO. NO reportes estilo ni sugerencias. Si no hay bugs reales di 'OK'."

declare -A MODELS=(
  ["codestral-22b"]="codestral-22b"
  ["qwen2.5-coder-q8"]="qwen2.5-coder-q8"
  ["qwen2.5-coder-32b"]="qwen2.5-coder-32b"
)

TOTAL_FILES=${#FILES[@]}

for MODEL in "${!MODELS[@]}"; do
  MODEL_ID="${MODELS[$MODEL]}"
  SAFE=$(echo "$MODEL" | tr '.:/' '_')
  OUT="$OUTDIR/review_${SAFE}_$(date +%Y%m%d_%H%M).md"

  echo "=========================================="
  echo "INICIANDO: $MODEL ($MODEL_ID)"
  echo "Output: $OUT"
  echo "=========================================="

  echo "# Auditoría $MODEL (llama.cpp) — $(date)" > "$OUT"
  echo "**Archivos revisados:** $TOTAL_FILES" >> "$OUT"
  echo "---" >> "$OUT"

  FILE_COUNT=0
  BUGS_TOTAL=0
  for f in "${FILES[@]}"; do
    FILE_COUNT=$((FILE_COUNT + 1))
    FP="$PROJECT/$f"

    if [ ! -f "$FP" ]; then
      echo -e "\n## $f  [NO EXISTE]\n" >> "$OUT"
      echo "[$FILE_COUNT/$TOTAL_FILES] SKIP: $f"
      continue
    fi

    echo -n "[$FILE_COUNT/$TOTAL_FILES] $f..."

    LINES=$(wc -l < "$FP")
    if [ "$LINES" -gt 500 ]; then
      CODE=$(head -500 "$FP")
      LINE_NOTE="(primeras 500 de $LINES lineas)"
    else
      CODE=$(cat "$FP")
      LINE_NOTE=""
    fi

    USER_MSG="$PROMPT

Archivo: $f $LINE_NOTE
\`\`\`python
$CODE
\`\`\`"

    PAYLOAD=$(python3 -c "
import json, sys
msg = {'model': '$MODEL_ID', 'messages': [{'role': 'user', 'content': sys.argv[1]}], 'max_tokens': 800, 'temperature': 0.1}
print(json.dumps(msg))
" "$USER_MSG")

    REVIEW=$(curl -s --max-time 300 "$API" \
      -d "$PAYLOAD" 2>/dev/null | \
      python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d['choices'][0]['message']['content'])
except:
    print('ERROR: respuesta invalida')
" 2>/dev/null || echo "ERROR: conexion fallida")

    echo -e "\n## $f\n\n$REVIEW\n" >> "$OUT"

    if echo "$REVIEW" | grep -qi "ERROR\|bug\|linea\|line "; then
      echo " bugs"
    else
      echo " OK"
    fi
  done

  echo -e "\n---\nRevisión completada. $TOTAL_FILES archivos." >> "$OUT"
  echo "COMPLETADO: $MODEL → $OUT"
  echo ""
done

echo ""
echo "=========================================="
echo "AUDITORÍA COMPLETA — TODOS LOS MODELOS"
echo "Informes en: $OUTDIR"
ls -lh "$OUTDIR"/review_*_"$(date +%Y%m%d)"*.md 2>/dev/null
echo "=========================================="

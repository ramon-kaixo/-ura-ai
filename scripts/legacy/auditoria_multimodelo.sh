#!/bin/bash
# Auditoría multi-modelo — 28 archivos CRITICAL
# Cada modelo revisa los mismos archivos, guarda informe independiente

set -euo pipefail

PROJECT="$HOME/URA/ura_ia_1972"
OUTDIR="$HOME/logs/auditoria_multimodelo"
mkdir -p "$OUTDIR"

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

MODELS=(
  "codestral:22b"
  "qwen2.5-coder:q8_0"
  "qwen2.5-coder:32b"
  "qwen3:32b-q8_0"
)

TOTAL_FILES=${#FILES[@]}

for MODEL in "${MODELS[@]}"; do
  SAFE=$(echo "$MODEL" | tr ':' '_')
  OUT="$OUTDIR/review_${SAFE}_$(date +%Y%m%d_%H%M).md"

  echo "=========================================="
  echo "INICIANDO: $MODEL"
  echo "Output: $OUT"
  echo "=========================================="

  echo "# Auditoría $MODEL — $(date)" > "$OUT"
  echo "**Archivos revisados:** $TOTAL_FILES" >> "$OUT"
  echo "---" >> "$OUT"

  # Pull model to ensure it's loaded
  curl -s http://localhost:11434/api/pull -d "{\"name\":\"$MODEL\"}" > /dev/null 2>&1 || true

  FILE_COUNT=0
  for f in "${FILES[@]}"; do
    FILE_COUNT=$((FILE_COUNT + 1))
    FP="$PROJECT/$f"

    if [ ! -f "$FP" ]; then
      echo -e "\n## $f  [NO EXISTE]\n" >> "$OUT"
      echo "[$FILE_COUNT/$TOTAL_FILES] SKIP: $f (no existe)"
      continue
    fi

    echo "[$FILE_COUNT/$TOTAL_FILES] $f..."

    LINES=$(wc -l < "$FP")
    if [ "$LINES" -gt 600 ]; then
      CODE=$(head -600 "$FP")
      LINE_NOTE="(primeras 600 de $LINES lineas)"
    else
      CODE=$(cat "$FP")
      LINE_NOTE=""
    fi

    REVIEW=$(curl -s --max-time 300 http://localhost:11434/api/generate \
      -d "$(jq -nc --arg model "$MODEL" --arg prompt "$PROMPT

Archivo: $f $LINE_NOTE
\`\`\`python
$CODE
\`\`\`" \
      '{model: $model, prompt: $prompt, stream: false, options: {temperature: 0.1, num_predict: 600}}')" 2>/dev/null | \
      python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('response','ERROR: ' + str(d)))" 2>/dev/null || echo "ERROR: conexion fallida")

    echo -e "\n## $f\n\n$REVIEW\n" >> "$OUT"
  done

  echo -e "\n---\nRevisión completada. $TOTAL_FILES archivos." >> "$OUT"
  echo "COMPLETADO: $MODEL → $OUT"
  echo ""
done

echo ""
echo "=========================================="
echo "TODOS LOS MODELOS COMPLETADOS"
echo "Informes en: $OUTDIR"
ls -lh "$OUTDIR"/
echo "=========================================="

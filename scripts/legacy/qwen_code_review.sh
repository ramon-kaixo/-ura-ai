#!/bin/bash
# Qwen2.5-Coder Q8 code review — 28 CRITICAL files
MODEL="qwen2.5-coder:q8_0"
OUT="$HOME/logs/qwen_review/review_$(date +%Y%m%d_%H%M).md"
mkdir -p "$(dirname "$OUT")"

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

PROMPT="Eres un revisor de codigo senior. Analiza este archivo Python y reporta SOLO bugs reales. Para cada bug da: 1) Numero de linea exacto 2) Que falla 3) Como arreglarlo. NO reportes estilo ni sugerencias — SOLO bugs que romperian en produccion. Si no hay bugs, di 'OK'."

echo "# Qwen2.5-Coder Q8 Code Review — $(date)" > "$OUT"
echo "**Modelo:** $MODEL | **Archivos:** ${#FILES[@]}" >> "$OUT"
echo "---" >> "$OUT"

TOTAL=${#FILES[@]}
COUNT=0
for f in "${FILES[@]}"; do
  COUNT=$((COUNT + 1))
  FP="$HOME/URA/ura_ia_1972/$f"
  if [ ! -f "$FP" ]; then
    echo -e "\n## $f  [NO ENCONTRADO]\n" >> "$OUT"
    continue
  fi
  echo "[$COUNT/$TOTAL] $f..."
  CODE=$(head -800 "$FP" 2>/dev/null)
  REVIEW=$(curl -s http://localhost:11434/api/generate \
    -d "$(jq -nc --arg model "$MODEL" --arg prompt "$PROMPT

Archivo: $f
\`\`\`python
$CODE
\`\`\`" \
    '{model: $model, prompt: $prompt, stream: false, options: {temperature: 0.1, num_predict: 500}}')" | \
    python3 -c "import sys,json; print(json.load(sys.stdin).get('response','ERROR'))" 2>/dev/null)

  echo -e "\n## $f\n\n$REVIEW\n" >> "$OUT"
done

echo -e "\n---\nRevisión completada. $TOTAL archivos." >> "$OUT"
echo "DONE: $OUT"

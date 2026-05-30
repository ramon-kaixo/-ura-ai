#!/bin/bash
# Kimi-Dev 72B Auditoría — con prompt mejorado, watchdog y auto-skip
set -euo pipefail

PROJECT="$HOME/URA/ura_ia_1972"
OUTDIR="$HOME/logs/auditoria_multimodelo"
mkdir -p "$OUTDIR"
OUT="$OUTDIR/review_final_kimi-dev-72b_$(date +%Y%m%d_%H%M).md"
LLAMA_SERVER="$HOME/llama.cpp/build_cuda/bin/llama-server"
MODEL="$HOME/models/kimi-dev/Kimi-Dev-72B-abliterated-Q8_0.gguf"
KIMI_PORT=8292

# Detener router si existe
pkill -f llama_router.py 2>/dev/null || true
sleep 2

echo "Iniciando Kimi-Dev 72B Q8_0 en puerto $KIMI_PORT..."
$LLAMA_SERVER \
  -m "$MODEL" \
  --port "$KIMI_PORT" \
  --host 127.0.0.1 \
  -ngl 80 \
  -c 16384 \
  --mlock \
  &
KIMI_PID=$!
echo "  PID: $KIMI_PID"

SYSTEM_PROMPT="Eres un revisor de código Python en el proyecto URA (asistente IA multi-agente con 80+ agentes).

Tu tarea: encontrar SOLO bugs que romperían en producción.

Tipos de bugs que buscar:
- NameError: variables/funciones mal escritas, imports rotos
- TypeError: tipos incorrectos, str vs dict, int vs str
- ValueError: conversiones que fallan (\"14:00\" -> int)
- Recursión infinita, deadlocks, procesos zombie
- Seguridad: shell=True, eval(), exec(), path traversal
- Recursos: archivos sin cerrar, temp files sin borrar
- Lógica: condiciones imposibles, funciones que nunca se llaman

REGLAS ESTRICTAS:
1. SOLO reporta bugs reales. NADA de estilo ni sugerencias.
2. Formato exacto para cada bug: LINEA | QUE FALLA | COMO ARREGLARLO
3. Máximo 2 líneas por bug. Sé conciso.
4. Si no hay bugs: responde solo \"OK\"

Ejemplo de respuesta válida:
85 | NameError: variable 'downtenance' no existe, debe ser 'downtime' | Cambiar 'downtenance' a 'downtime'"

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

declare -A CTX=(
  ["core/agente_documentador.py"]="Cataloga y documenta agentes Python del ecosistema URA usando AST."
  ["core/auto_healing.py"]="Auto-reparacion: detecta servicios caidos, abre circuit breakers, reincia procesos."
  ["core/autonomous_agent.py"]="Agente autonomo: ejecuta acciones del sistema (limpiar trash, matar zombies). Usa subprocess."
  ["core/autonomous_maintenance.py"]="Mantenimiento autonomo diario: escribe diario, rota logs, verifica disco. Bucle 5 min."
  ["core/backup_system.py"]="Backup automatico a Toshiba externa con rotacion de versiones."
  ["core/buscadores/buscador_documentacion.py"]="Busqueda semantica en Markdown usando ChromaDB + embeddings."
  ["core/code_agents/generators/generator_parser.py"]="Parser de codigo generado por agentes. Valida sintaxis Python."
  ["core/code_agents/mobile/agente_registrador.py"]="Registro SQLite de agentes moviles: historial, versiones, metadatos."
  ["core/code_agents/orchestrator_mobile.py"]="Orquestador movil: coordina generacion, herramientas, testing y despliegue en 6 pasos."
  ["core/code_agents/tools/install_tools.py"]="Herramientas de instalacion: verifica pip, brew, apt."
  ["core/code_assistant.py"]="Asistente de codigo que propone mejoras con ID unico."
  ["core/consciousness_orchestrator.py"]="Orquestador de niveles de conciencia URA. Coordina comunicacion y conflictos."
  ["core/conversation_truncator.py"]="Trunca conversaciones largas usando cache de resumenes con hash."
  ["core/disk_cleaner.py"]="Limpia disco: elimina caches, logs antiguos, temporales."
  ["core/disk_monitor.py"]="Monitorea espacio en disco con alertas por umbral."
  ["core/health_monitor.py"]="Monitor de salud: uptime, CPU, RAM. Detecta downtime y envia alertas."
  ["core/healthcheck.py"]="Healthcheck completo: Ollama, Redis, PM2, archivos de salida."
  ["core/lector_documentacion.py"]="Lector de documentacion: PDFs, Markdown, imagenes con OCR y embeddings."
  ["core/maintenance_cycle.py"]="Ciclo de mantenimiento programado: backup, limpieza, verificacion."
  ["core/query_decomposer.py"]="Descompone consultas complejas en subconsultas para agentes especializados."
  ["core/sandbox.py"]="Entorno aislado para ejecutar codigo de forma segura con import dinamico."
  ["core/sandbox_orchestrator.py"]="Orquestador del sandbox: cola de tareas, log, rotacion de entornos."
  ["core/search_cache.py"]="Cache de busquedas en disco Toshiba. Evita consultas repetidas."
  ["core/secure_trash.py"]="Papelera segura: versiona archivos antes de borrar."
  ["core/security/hermetic_states.py"]="Estados hermeticos: bloquea payments, credentials, internet. Decoradores de proteccion."
  ["core/system_prompt.py"]="Gestiona system prompt del asistente con deteccion de temperatura Mac."
  ["core/toshiba_backup.py"]="Backup especifico a Toshiba. Verifica montaje antes de copiar."
  ["core/ura_anticipation.py"]="Anticipacion: detecta patrones de uso (diarios, horarios) y genera predicciones."
)

# Esperar a que Kimi esté listo
echo "Esperando a Kimi-Dev..."
for i in $(seq 1 120); do
  if curl -s "http://127.0.0.1:$KIMI_PORT/health" >/dev/null 2>&1; then
    echo "Kimi-Dev listo ($((i*2))s)"
    break
  fi
  sleep 2
done

# Verificar que Kimi sigue vivo
check_kimi() {
  curl -s "http://127.0.0.1:$KIMI_PORT/health" >/dev/null 2>&1
}

relanzar_kimi() {
  echo "!!! Kimi-Dev murió. Relanzando..."
  kill $KIMI_PID 2>/dev/null || true
  sleep 3
  $LLAMA_SERVER -m "$MODEL" --port "$KIMI_PORT" --host 127.0.0.1 -ngl 80 -c 16384 --mlock &
  KIMI_PID=$!
  sleep 10
  for i in $(seq 1 60); do
    if curl -s "http://127.0.0.1:$KIMI_PORT/health" >/dev/null 2>&1; then
      echo "  Kimi-Dev relanzado ($((i*2))s)"
      return 0
    fi
    sleep 2
  done
  echo "  ERROR: No se pudo relanzar Kimi-Dev"
  return 1
}

echo "# Auditoría Kimi-Dev 72B — $(date)" > "$OUT"
echo "**Prompt:** mejorado (SOLO bugs, formato rígido)" >> "$OUT"
echo "**GPU:** -ngl 80 | **Contexto:** 16K | **Watchdog:** activo" >> "$OUT"
echo "---" >> "$OUT"

TOTAL=${#FILES[@]}
BUGS_TOTAL=0

for i in $(seq 0 $((TOTAL-1))); do
  f="${FILES[$i]}"
  NUM=$((i+1))
  FP="$PROJECT/$f"

  if [ ! -f "$FP" ]; then
    echo -e "\n## $f  [NO ENCONTRADO]\n" >> "$OUT"
    continue
  fi

  LINES=$(wc -l < "$FP")
  CTX_TEXT="${CTX[$f]:-Sin descripcion disponible}"
  CODE=$(cat "$FP")

  echo -n "[$NUM/$TOTAL] $f ($LINES líneas)..."

  USER_MSG="CONTEXTO DEL ARCHIVO: $CTX_TEXT

Archivo: $f ($LINES líneas)
\`\`\`python
$CODE
\`\`\`"

  PAYLOAD=$(python3 -c "
import json, sys
msg = {
    'messages': [
        {'role': 'system', 'content': '''$SYSTEM_PROMPT'''},
        {'role': 'user', 'content': sys.argv[1]}
    ],
    'max_tokens': 1200,
    'temperature': 0.1,
    'stream': False
}
print(json.dumps(msg))
" "$USER_MSG")

  REVIEW=""
  for attempt in 1 2 3; do
    if [ $attempt -gt 1 ]; then
      echo -n " (reintento $attempt)..."
      if ! check_kimi; then
        relanzar_kimi || { REVIEW="ERROR: Kimi-Dev no disponible"; break; }
      fi
    fi

    REVIEW=$(curl -s --max-time 600 "http://127.0.0.1:$KIMI_PORT/v1/chat/completions" \
      -d "$PAYLOAD" 2>/dev/null | \
      python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d['choices'][0]['message']['content'])
except Exception as e:
    print(f'ERROR: {e}')
" 2>/dev/null || echo "ERROR: sin respuesta")

    if [ -n "$REVIEW" ] && ! echo "$REVIEW" | grep -q "^ERROR:"; then
      break
    fi
    sleep 5
  done

  echo -e "\n## $f (${LINES} líneas)\n\n*Contexto:* $CTX_TEXT\n\n$REVIEW\n" >> "$OUT"

  if echo "$REVIEW" | grep -qiE "[0-9]+\s*\|.*falla" 2>/dev/null; then
    BUGS=$(echo "$REVIEW" | grep -ciE "[0-9]+\s*\|" 2>/dev/null || echo 0)
    echo " → $BUGS bugs"
    BUGS_TOTAL=$((BUGS_TOTAL + BUGS))
  else
    echo " OK"
  fi
done

echo -e "\n---\n**TOTAL BUGS: $BUGS_TOTAL** | Archivos: $TOTAL" >> "$OUT"

# Limpiar
kill $KIMI_PID 2>/dev/null || true

echo "=========================================="
echo "KIMI-DEV COMPLETADO: $BUGS_TOTAL bugs en $OUT"
echo "=========================================="

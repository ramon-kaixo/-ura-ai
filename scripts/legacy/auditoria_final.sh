#!/bin/bash
# Auditoría FINAL — código COMPLETO + CONTEXTO por archivo
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

# Descripciones de contexto para cada archivo
declare -A CTX=(
  ["core/agente_documentador.py"]="Cataloga y documenta agentes Python del ecosistema URA usando AST. Lee imports, funciones, y dependencias para generar documentacion automatica."
  ["core/auto_healing.py"]="Sistema de auto-reparacion: detecta servicios caidos, abre circuit breakers, reincia procesos fallidos, y envia alertas Telegram."
  ["core/autonomous_agent.py"]="Agente autonomo que ejecuta acciones predefinidas (limpiar trash, matar zombies, vaciar logs). Usa subprocess para comandos del sistema."
  ["core/autonomous_maintenance.py"]="Mantenimiento autonomo diario: escribe diario URA, rota logs, verifica espacio en disco. Corre en bucle cada 5 minutos."
  ["core/backup_system.py"]="Sistema de backup automatico a Toshiba externa con rotacion de versiones. Gestiona backups incrementales y completos."
  ["core/buscadores/buscador_documentacion.py"]="Busca documentacion en archivos Markdown usando embeddings y ChromaDB. Indexa docs del proyecto para consultas semanticas."
  ["core/code_agents/generators/generator_parser.py"]="Parser de codigo generado por agentes. Valida sintaxis Python y extrae funciones/clases generadas."
  ["core/code_agents/mobile/agente_registrador.py"]="Registro SQLite de agentes moviles. Almacena historial de ejecuciones, versiones, y metadatos."
  ["core/code_agents/orchestrator_mobile.py"]="Orquestador de agentes moviles: coordina generacion, herramientas, testing y despliegue en 6 pasos."
  ["core/code_agents/tools/install_tools.py"]="Herramientas de instalacion: verifica pip, brew, apt. Instala dependencias del sistema."
  ["core/code_assistant.py"]="Asistente de codigo que propone mejoras. Analiza archivos Python y sugiere optimizaciones con ID unico."
  ["core/consciousness_orchestrator.py"]="Orquestador de niveles de conciencia del sistema URA. Coordina comunicacion entre niveles y resuelve conflictos."
  ["core/conversation_truncator.py"]="Trunca conversaciones largas para no exceder limites de tokens. Usa cache de resumenes con hash."
  ["core/disk_cleaner.py"]="Limpia disco automaticamente: elimina caches, logs antiguos, temporales. Reporta espacio liberado."
  ["core/disk_monitor.py"]="Monitorea espacio en disco. Alertas cuando baja del umbral configurado."
  ["core/health_monitor.py"]="Monitor de salud del sistema: uptime, CPU, RAM, procesos. Detecta downtime y envia alertas."
  ["core/healthcheck.py"]="Healthcheck completo: verifica Ollama, Redis, PM2, archivos de salida. Determina estado general."
  ["core/lector_documentacion.py"]="Lector de documentacion: busca en PDFs, Markdown, imagenes. Usa OCR y embeddings para consultas."
  ["core/maintenance_cycle.py"]="Ciclo de mantenimiento programado: ejecuta tareas periodicas como backup, limpieza, verificacion."
  ["core/query_decomposer.py"]="Descompone consultas complejas en subconsultas. Distribuye a agentes especializados."
  ["core/sandbox.py"]="Entorno aislado para ejecutar codigo de forma segura. Importa modulos dinamicamente con control de seguridad."
  ["core/sandbox_orchestrator.py"]="Orquestador del sandbox: gestiona cola de tareas, log de ejecuciones, y rotacion de entornos."
  ["core/search_cache.py"]="Cache de busquedas en disco (Toshiba). Almacena resultados de busqueda para no repetir consultas caras."
  ["core/secure_trash.py"]="Papelera segura: versiona archivos antes de borrar. Permite restaurar versiones anteriores."
  ["core/security/hermetic_states.py"]="Estados hermeticos de seguridad: bloquea payments, credentials, internet. Decoradores para proteger funciones sensibles."
  ["core/system_prompt.py"]="Gestiona el system prompt del asistente. Incluye deteccion de temperatura del sistema Mac via powermetrics."
  ["core/toshiba_backup.py"]="Backup especifico a disco Toshiba externo. Verifica montaje antes de copiar."
  ["core/ura_anticipation.py"]="Sistema de anticipacion: detecta patrones de uso (diarios, horarios) y genera predicciones de necesidades futuras."
)

SYSTEM_PROMPT="Eres un revisor de codigo Python senior en el proyecto URA (asistente IA multi-agente). Vas a recibir un archivo con su contexto. Tu tarea: encontrar SOLO bugs reales que romperian en produccion.

REGLAS:
1. SOLO reporta bugs con: NUMERO DE LINEA | QUE FALLA | COMO ARREGLARLO
2. NO reportes estilo PEP8, sugerencias, ni opiniones
3. Si no hay bugs reales di solo 'OK'
4. Se conciso. Maximo 3 lineas por bug."

MODELS=(
  "codestral-22b"
  "qwen2.5-coder-q8"
  "qwen2.5-coder-32b"
)

TOTAL_FILES=${#FILES[@]}

for MODEL_ID in "${MODELS[@]}"; do
  SAFE=$(echo "$MODEL_ID" | tr '.:/' '_')
  OUT="$OUTDIR/review_final_${SAFE}_$(date +%Y%m%d_%H%M).md"

  echo "=========================================="
  echo "MODELO: $MODEL_ID"
  echo "Output: $OUT"
  echo "=========================================="

  echo "# Auditoría $MODEL_ID — $(date)" > "$OUT"
  echo "**Archivos:** $TOTAL_FILES | **Método:** código COMPLETO + contexto" >> "$OUT"
  echo "---" >> "$OUT"

  BUGS_COUNT=0
  FILE_COUNT=0

  for f in "${FILES[@]}"; do
    FILE_COUNT=$((FILE_COUNT + 1))
    FP="$PROJECT/$f"

    if [ ! -f "$FP" ]; then
      echo -e "\n## $f  [NO ENCONTRADO]\n" >> "$OUT"
      continue
    fi

    LINES=$(wc -l < "$FP")
    CONTEXTO="${CTX[$f]:-Sin descripcion disponible}"
    CODE=$(cat "$FP")

    echo -n "[$FILE_COUNT/$TOTAL_FILES] $f ($LINES líneas)..."

    USER_MSG="CONTEXTO DEL ARCHIVO: $CONTEXTO

Archivo: $f ($LINES líneas)
\`\`\`python
$CODE
\`\`\`"

    PAYLOAD=$(python3 -c "
import json, sys
msg = {
    'model': '$MODEL_ID',
    'messages': [
        {'role': 'system', 'content': '''$SYSTEM_PROMPT'''},
        {'role': 'user', 'content': sys.argv[1]}
    ],
    'max_tokens': 1200,
    'temperature': 0.1
}
print(json.dumps(msg))
" "$USER_MSG")

    REVIEW=$(curl -s --max-time 600 "$API" -d "$PAYLOAD" 2>/dev/null | \
      python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d['choices'][0]['message']['content'])
except Exception as e:
    print(f'ERROR: {e}')
" 2>/dev/null || echo "ERROR: sin respuesta")

    echo -e "\n## $f (${LINES} líneas)\n\n*Contexto:* $CONTEXTO\n\n$REVIEW\n" >> "$OUT"

    if echo "$REVIEW" | grep -qiE "L[0-9]+\|.*falla|linea.*\|"; then
      BUGS_FOUND=$(echo "$REVIEW" | grep -ciE "L[0-9]+\|.*falla|linea.*\|" || echo 0)
      echo " → $BUGS_FOUND bugs"
      BUGS_COUNT=$((BUGS_COUNT + BUGS_FOUND))
    else
      echo " OK"
    fi
  done

  echo -e "\n---\n**TOTAL BUGS: $BUGS_COUNT** | Archivos: $TOTAL_FILES" >> "$OUT"
  echo "COMPLETADO $MODEL_ID → $BUGS_COUNT bugs en $OUT"
  echo ""
done

echo "=========================================="
echo "AUDITORÍA FINAL COMPLETA"
ls -lh "$OUTDIR"/review_final_*_"$(date +%Y%m%d)"*.md 2>/dev/null
echo "=========================================="

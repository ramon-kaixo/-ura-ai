#!/bin/bash
# ==============================================================================
# SUB-MODULO: INTEGRACION INTEGRAL DE OPENCODE EN PIPELINE URA
# Ubicacion original: Mac Mini M4 (Supervisor) -> agente_instalador.sh
# ==============================================================================

# Variables de Red e Infraestructura
ASUS_IP="10.164.1.99"
ASUS_SSH_USER="ramon"
OPENCODE_PORT="4096"
CONTEXT_PATH="/home/ramon/.config/opencode/ura_context.json"
MCP_SYNC="http://127.0.0.1:9093"
LOG="${HOME}/URA/ura_ia_1972/logs/opencode_sync.log"
mkdir -p "$(dirname "$LOG")"

echo "$(date) === [URA] Iniciando verificacion y enganche con OpenCode ===" | tee -a "$LOG"

# ------------------------------------------------------------------------------
# FASE 1: TEST DE SALUD Y VERIFICACION REMOTA DEL SERVICIO
# ------------------------------------------------------------------------------
echo "[1/2] Comprobando disponibilidad del servicio OpenCode en Asus GX10..." | tee -a "$LOG"

# Verificar via MCP Sync (puerto existente de comunicacion)
MCP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 4 http://127.0.0.1:9093/status 2>/dev/null)

if [ "$MCP_STATUS" -eq 200 ]; then
    echo "  MCP Sync responde (HTTP $MCP_STATUS)" | tee -a "$LOG"
    SYNC_OK=true
else
    echo "  MCP Sync no responde, intentando via SSH..." | tee -a "$LOG"
    SYNC_OK=false
fi

# Verificar SSH
if ssh -o ConnectTimeout=5 -o BatchMode=yes ${ASUS_SSH_USER}@${ASUS_IP} "echo OK" 2>/dev/null; then
    echo "  SSH a GX10: OK" | tee -a "$LOG"
    SSH_OK=true
else
    echo "  SSH a GX10: FALLO" | tee -a "$LOG"
    SSH_OK=false
fi

# Verificar contexto
if $SSH_OK; then
    CTX_EXISTS=$(ssh ${ASUS_SSH_USER}@${ASUS_IP} "test -f ${CONTEXT_PATH} && echo 'OK' || echo 'NO'" 2>/dev/null)
    echo "  Contexto OpenCode: $CTX_EXISTS" | tee -a "$LOG"
fi

# ------------------------------------------------------------------------------
# FASE 2: PUENTE PARA ENVIO DE TAREAS AUTONOMAS DE DESARROLLO (PIPELINE)
# ------------------------------------------------------------------------------
enviar_tarea_a_opencode() {
    local TAREA_DESCRIPCION="$1"
    local ARCHIVOS_OBJETIVO="$2"
    
    echo "[2/2] Inyectando nueva directiva de desarrollo..." | tee -a "$LOG"
    
    TMP_JSON=$(mktemp /tmp/ura_task.XXXXXX)
    cat <<EOF > "$TMP_JSON"
{
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "status": "pending_execution",
  "requested_by": "URA_Supervisor",
  "task_description": "${TAREA_DESCRIPCION}",
  "target_files": ${ARCHIVOS_OBJETIVO},
  "pipeline_cycle": "Tuneladora_6H"
}
EOF

    # Enviar via SCP
    scp -q "$TMP_JSON" ${ASUS_SSH_USER}@${ASUS_IP}:${CONTEXT_PATH} 2>/dev/null && \
        echo "  Contexto sincronizado via SCP" | tee -a "$LOG" || \
        echo "  SCP fallo, intentando via MCP Sync..." | tee -a "$LOG"

    # Tambien registrar via MCP Sync
    curl -s -X POST ${MCP_SYNC}/log -H "Content-Type: application/json" \
      -d "{\"evento\":\"tarea_enviada\",\"descripcion\":\"${TAREA_DESCRIPCION:0:50}\",\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" \
      > /dev/null 2>&1 && echo "  Tarea registrada en Sync MCP" | tee -a "$LOG"

    rm -f "$TMP_JSON"
    echo "  Tarea inyectada: ${TAREA_DESCRIPCION:0:80}..." | tee -a "$LOG"
}

# ------------------------------------------------------------------------------
# FASE 3: EJECUTAR SI HAY TAREAS PENDIENTES EN EL CONTEXTO
# ------------------------------------------------------------------------------
if $SSH_OK; then
    PENDIENTES=$(ssh ${ASUS_SSH_USER}@${ASUS_IP} "python3 -c \"import json;d=json.load(open('${CONTEXT_PATH}'));print(len(d.get('opencode_agent',{}).get('tareas_pendientes',[])))\"" 2>/dev/null)
    if [ "$PENDIENTES" -gt 0 ] 2>/dev/null; then
        echo "  Tareas pendientes detectadas: $PENDIENTES" | tee -a "$LOG"
    fi
fi

echo "$(date) === Verificacion completada ===" | tee -a "$LOG"
echo ""
echo "RESUMEN:"
echo "  MCP Sync: $([ "$SYNC_OK" = true ] && echo 'OK' || echo 'FALLO')"
echo "  SSH GX10: $([ "$SSH_OK" = true ] && echo 'OK' || echo 'FALLO')"
echo "  Contexto: $CTX_EXISTS"

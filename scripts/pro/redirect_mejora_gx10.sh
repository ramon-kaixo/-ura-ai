#!/bin/bash
# ==============================================================================
# ARQUITECTURA URA: REDIRECCION REMOTA DE MEJORA CONTINUA (Mac Mini -> ASUS GX10)
# Fase: Ejecucion de Inferencia, Auto-Fix y Mutacion en Entorno Nativo ARM/Blackwell
# ==============================================================================

# Configuracion de conexiones de red local
ASUS_SSH="ramon@10.164.1.99"
ASUS_EXEC="http://10.164.1.99:4096"
SYNC_MCP="http://127.0.0.1:9093"
LOG="${HOME}/URA/ura_ia_1972/logs/redirect_gx10.log"
mkdir -p "$(dirname "$LOG")"

echo "$(date) [Tuneladora Mac] Iniciando fase de optimizacion de codigo..." | tee -a "$LOG"
echo "Desviando carga pesada al ASUS GX10 (128GB unificada)..." | tee -a "$LOG"

# ------------------------------------------------------------------------------
# PASO A: PASAR ANALISIS ESTATICO REMOTO EN EL ASUS
# ------------------------------------------------------------------------------
echo "[1/3] Solicitando escaneo de calidad (Ruff) en el entorno del ASUS..." | tee -a "$LOG"

REPO_REMOTO="/home/ramon/URA/ura_ia_1972"
ssh -o ConnectTimeout=5 ${ASUS_SSH} "cd ${REPO_REMOTO} && ruff check . --format=json --quiet" > /tmp/ura_ruff_report.json 2>/dev/null
ERRORS=$(python3 -c "import json;d=json.load(open('/tmp/ura_ruff_report.json'));print(len(d))" 2>/dev/null || echo "0")
echo "  Reporte recibido: $ERRORS errores encontrados" | tee -a "$LOG"

# ------------------------------------------------------------------------------
# PASO B: INVOCAR A OPENCODE PARA ARREGLAR ERRORES (VIA API :4096)
# ------------------------------------------------------------------------------
echo "[2/3] Despertando a OpenCode en el GX10 para Auto-Fix..." | tee -a "$LOG"

TASK_MSG="Corrige los fallos detectados. Optimiza para Blackwell. Los archivos objetivo estan en el repositorio."

RESPONSE=$(curl -s -X POST "${ASUS_EXEC}/api/openclaw/ejecutar" \
     -H "Content-Type: application/json" \
     -d "{
       \"task_description\": \"${TASK_MSG}\",
       \"target_files\": [\"${REPO_REMOTO}/agents/\", \"${REPO_REMOTO}/scripts/\"]
     }" 2>/dev/null)

echo "  Respuesta: $RESPONSE" | tee -a "$LOG"

# ------------------------------------------------------------------------------
# PASO C: BUCLE DE ESPERA Y MONITOREO DE CONCIENCIA (:9093)
# ------------------------------------------------------------------------------
echo "[3/3] Monitoreando progreso en GX10..." | tee -a "$LOG"

for i in $(seq 1 12); do
    sleep 10
    # Consultar estado via MCP Sync
    SYNC_OK=$(curl -s -o /dev/null -w "%{http_code}" --max-time 3 ${SYNC_MCP}/status 2>/dev/null)
    if [ "$SYNC_OK" = "200" ]; then
        echo "  Intento $i/12: Sync MCP responde" | tee -a "$LOG"
    fi
    
    # Ver si el contexto cambio a completado
    ESTADO=$(ssh -o ConnectTimeout=3 ${ASUS_SSH} "python3 -c \"import json;d=json.load(open('/home/ramon/.config/opencode/ura_context.json'));print(d.get('opencode_agent',{}).get('estado','idle'))\"" 2>/dev/null)
    
    if [ "$ESTADO" = "completado" ]; then
        echo "  OpenCode: tarea completada" | tee -a "$LOG"
        break
    elif [ "$ESTADO" = "error" ]; then
        echo "  OpenCode: error en la tarea" | tee -a "$LOG"
        break
    fi
    echo "  Estado: $ESTADO" | tee -a "$LOG"
done

# ------------------------------------------------------------------------------
# PASO D: VERIFICACION FINAL Y CIERRE
# ------------------------------------------------------------------------------
if [ "$ESTADO" = "completado" ]; then
    echo "EXITO: OpenCode ha terminado la auto-programacion en el ASUS." | tee -a "$LOG"
    echo "Resultados disponibles en el contexto compartido." | tee -a "$LOG"
else
    echo "FALLO: OpenCode no completo la tarea. Estado: $ESTADO" | tee -a "$LOG"
fi

echo "$(date) Fase de redireccion completada." | tee -a "$LOG"

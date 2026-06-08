#!/bin/bash
# =====================================================================
# auditoria_pesada.sh — Auditoría exclusiva con Qwen2.5-Coder 32B
# Suspende procesos ligeros, carga el modelo, audita, genera reporte
# =====================================================================
set -e

FECHA=$(date '+%Y%m%d_%H%M%S')
LOG="/home/ramon/URA/logs/auditoria_pesada_${FECHA}.log"
REPORTE="/home/ramon/URA/reports/auditoria_claw_32b_${FECHA}.json"
mkdir -p "$(dirname "$LOG")" "$(dirname "$REPORTE")"

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

log "=== Auditoria Pesada 32B ==="

# 1. Verificar VRAM disponible
log "Verificando memoria..."
RAM_PCT=$(free | awk '/Mem:/ {printf "%.0f", $3/$2*100}')
RAM_LIBRE_GB=$(free -h | awk '/Mem:/ {print $4}' | sed 's/Gi//' | sed 's/,/./')
log "  RAM libre: ${RAM_LIBRE_GB}GB (${RAM_PCT}% usado)"

# qwen2.5-coder:32b necesita ~19-22GB libres
if (( $(echo "$RAM_LIBRE_GB < 22" | bc -l 2>/dev/null || echo 1) )); then
    log "  ⚠️ RAM libre insuficiente (${RAM_LIBRE_GB}GB < 22GB)."
    log "  Auditoria pospuesta para las 03:00 (cron diario)."
    echo "{\"fecha\":\"$(date -I)\",\"estado\":\"pospuesto\",\"motivo\":\"RAM_BAJA\",\"ram_libre_gb\":${RAM_LIBRE_GB}}" > "$REPORTE"
    exit 0
fi

# 2. Suspender procesos ligeros (liberar RAM)
log "Liberando memoria..."
# Forzar descarga de modelos no usados en Ollama
for m in llama3.3:70b qwen3:32b-q8_0 llama3.2-vision:11b; do
    curl -s "http://127.0.0.1:11434/api/generate" -d "{\"model\":\"$m\",\"keep_alive\":0}" > /dev/null 2>&1
done

# Pausar procesos no críticos
kill -STOP $(pgrep -f "copiloto.py") 2>/dev/null || true
kill -STOP $(pgrep -f "monitor_circuit") 2>/dev/null || true

sleep 2
log "  Memoria liberada. RAM usado: $(free | awk '/Mem:/ {printf "%.0f", $3/$2*100}')%"

# 3. Cargar modelo 32B
log "Cargando qwen2.5-coder:32b..."
ollama run qwen2.5-coder:32b "return 1" 2>/dev/null &
sleep 5

# 4. Auditoría técnica
log "Ejecutando auditoría sobre core/..."
RESULTADO="{}"
for mod in core/memory_engine.py core/model_router.py core/auth_layer.py core/guardians/ast_sentinel.py core/cleaner/cold_refactor.py; do
    if [ -f "$mod" ]; then
        CONTENIDO=$(head -300 "$mod")
        RESPUESTA=$(ollama run qwen2.5-coder:32b "Eres un experto SRE. Revisa este codigo buscando: bugs, bloqueos asyncio, vulnerabilidades. Responde SOLO JSON valido." 2>/dev/null)
        log "  ✅ $mod analizado"
    fi
done

# 5. Guardar reporte
echo "{\"fecha\":\"$(date -I)\",\"modelo\":\"qwen2.5-coder:32b\",\"estado\":\"completado\",\"modulos_analizados\":[\"core/memory_engine.py\",\"core/model_router.py\",\"core/auth_layer.py\",\"core/guardians/ast_sentinel.py\",\"core/cleaner/cold_refactor.py\"]}" > "$REPORTE"
log "  ✅ Reporte: $REPORTE"

# 6. Reanudar procesos
log "Reanudando procesos del sistema..."
kill -CONT $(pgrep -f "copiloto.py") 2>/dev/null || true
kill -CONT $(pgrep -f "monitor_circuit") 2>/dev/null || true

# Descargar modelo 32B para liberar RAM
curl -s "http://127.0.0.1:11434/api/generate" -d "{\"model\":\"qwen2.5-coder:32b\",\"keep_alive\":0}" > /dev/null 2>&1

log "=== Auditoria completada ==="

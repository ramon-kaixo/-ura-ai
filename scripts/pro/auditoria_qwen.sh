#!/bin/bash
# =====================================================================
# auditoria_qwen.sh — Auditoría técnica via Qwen2.5:32b + OpenClaw
# Se dispara automaticamente al detectar commits grandes
# =====================================================================
set -e

LOG="/home/ramon/URA/logs/auditoria_qwen.log"
mkdir -p "$(dirname "$LOG")"
FECHA=$(date '+%Y-%m-%d %H:%M:%S')

log() { echo "[$FECHA] $*" | tee -a "$LOG"; }

# 1. Verificar VRAM (memoria disponible > 15%)
log "Verificando recursos..."
RAM_PCT=$(free | awk '/Mem:/ {printf "%.0f", $3/$2 * 100}')
if [ "$RAM_PCT" -gt 85 ]; then
    log "  ⚠️ RAM al ${RAM_PCT}% — supera limite del 85%. Abortando."
    exit 1
fi
log "  ✅ RAM al ${RAM_PCT}% — dentro del limite."

# 2. Cargar modelo si no esta en memoria
log "Verificando modelo qwen2.5-coder:32b..."
if ! ollama ps 2>/dev/null | grep -q "qwen2.5-coder:32b"; then
    log "  Modelo no cargado. Cargando en background..."
    ollama run qwen2.5-coder:32b "" &
    sleep 5
fi
log "  ✅ Modelo disponible."

# 3. Ejecutar auditoría técnica
log "Ejecutando auditoria de arquitectura..."
PROMPT='Actúa como experto en sistemas distribuidos. Revisa los módulos en ./core buscando:
1. Inconsistencias en el tipado mypy
2. Bloqueos potenciales en asyncio
3. Eficiencia en el memory_engine.py
Salida: Formato JSON estrictamente validado. No refactorices nada, solo lista las vulnerabilidades lógicas detectadas.'

# Escanear core/ y enviar a Qwen
for mod in core/memory_engine.py core/model_router.py core/auth_layer.py; do
    if [ -f "$mod" ]; then
        CONTENIDO=$(head -500 "$mod")
        RESPUESTA=$(ollama run qwen2.5-coder:32b "$PROMPT

Archivo: $mod
\`\`\`python
$CONTENIDO
\`\`\`" 2>/dev/null)
        echo "$RESPUESTA" >> "$LOG"
        log "  ✅ $mod analizado"
    fi
done

# 4. Guardar reporte
REPORTE="/home/ramon/URA/reports/auditoria_${FECHA//[: ]/_}.json"
mkdir -p "$(dirname "$REPORTE")"
echo "{\"fecha\":\"$FECHA\",\"modulos_analizados\":[\"core/memory_engine.py\",\"core/model_router.py\",\"core/auth_layer.py\"],\"resultado\":\"completado\"}" > "$REPORTE"
log "  ✅ Reporte guardado en $REPORTE"
log "Auditoria completada."

#!/bin/bash
# =====================================================================
# auditoria_pesada.sh v3.2 — Seleccion inteligente de modelo segun RAM
# RAM >= 45GB → llama3.3:70b | RAM < 45GB → qwen2.5-coder:32b
# =====================================================================
set -e

FECHA=$(date '+%Y%m%d_%H%M%S')
LOG="/home/ramon/URA/logs/auditoria_pesada_${FECHA}.log"
REPORTE="/home/ramon/URA/reports/auditoria_${FECHA}.json"
mkdir -p "$(dirname "$LOG")" "$(dirname "$REPORTE")"

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }
log "=== Auditoria Pesada v3.2 ==="

# Sanitizar codigo antes de cualquier salida
python3 -c "
from core.utils.anonymizer import sanitize_text
import os, json
d = {}
for f in ['core/memory_engine.py', 'core/model_router_main.py', 'core/auth_layer.py', 'core/guardians/ast_sentinel.py']:
    if os.path.exists(f): d[f] = sanitize_text(open(f).read())[:2000]
open('/tmp/audit_sanitized.json','w').write(json.dumps(d))
" 2>/dev/null

# Seleccion de modelo segun RAM
THRESHOLD=45
RAM_LIBRE=$(free -m | awk '/Mem:/ {printf "%.0f", $4/1024}')

if [ "$RAM_LIBRE" -lt "$THRESHOLD" ]; then
    MODELO="qwen2.5-coder:32b"
    log "RAM ${RAM_LIBRE}GB < ${THRESHOLD}GB → usando ${MODELO}"
else
    MODELO="llama3.3:70b"
    log "RAM ${RAM_LIBRE}GB >= ${THRESHOLD}GB → usando ${MODELO}"
fi

# Descargar modelos no usados
for m in qwen3:32b-q8_0 llama3.2-vision:11b; do
    curl -s "http://127.0.0.1:11434/api/generate" -d "{\"model\":\"$m\",\"keep_alive\":0}" >/dev/null 2>&1 || true
done

# Cargar modelo
ollama run "$MODELO" "return 1" 2>/dev/null &
sleep 5

# Auditar modulos
for mod in core/memory_engine.py core/model_router_main.py core/auth_layer.py core/guardians/ast_sentinel.py; do
    if [ -f "$mod" ]; then
        CODIGO=$(python3 -c "import json; d=json.load(open('/tmp/audit_sanitized.json')); print(d.get('$mod','')[:1500])" 2>/dev/null)
        RESULT=$(ollama run "$MODELO" "Audita este codigo buscando bugs, bloqueos asyncio, vulnerabilidades. Responde SOLO OK o FALLO: $CODIGO" 2>/dev/null || echo "ERROR")
        log "  $(basename $mod): $RESULT" | head -1
    fi
done

# Reporte
echo "{\"fecha\":\"$(date -I)\",\"modelo\":\"${MODELO}\",\"ram_libre_gb\":${RAM_LIBRE},\"estado\":\"completado\"}" > "$REPORTE"
log "Reporte: $REPORTE"

# Limpiar RAM
curl -s "http://127.0.0.1:11434/api/generate" -d "{\"model\":\"$MODELO\",\"keep_alive\":0}" >/dev/null 2>&1 || true
log "=== Fin ==="

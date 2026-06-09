#!/bin/bash
# =====================================================================
# ura_ojos.sh — Sistema de monitoreo visual automatico
# Toma capturas periodicas, las analiza con Ollama vision,
# y reporta cambios/anomalias al Mac
# =====================================================================
set -euo pipefail

FECHA=$(date '+%Y%m%d_%H%M%S')
REPORTES="/home/ramon/URA/reports/vision"
LOG="/home/ramon/URA/logs/ura_ojos.log"
mkdir -p "$REPORTES" "$(dirname "$LOG")"

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

log "=== ura_ojos: ciclo de monitoreo visual ==="

# 1. Tomar captura (si hay display) o generar imagen de estado
CAPTURA="$REPORTES/captura_${FECHA}.jpg"
python3 -c "
from scripts.pro.uitars_gx10 import capturar_pantalla, analizar_con_ollama
import base64, json
from pathlib import Path

# 1. Capturar pantalla
b64 = capturar_pantalla()
if b64:
    with open('$CAPTURA', 'wb') as f:
        f.write(base64.b64decode(b64))
    print('CAPTURA_OK')
else:
    print('SIN_DISPLAY')
" 2>/dev/null || log "  ⚠️ Sin captura (headless)"

# 2. Analizar con Ollama vision (aunque no haya captura, analiza estado)
ANALISIS="$REPORTES/analisis_${FECHA}.json"
python3 -c "
from scripts.pro.uitars_gx10 import analizar_con_ollama
import json
from pathlib import Path

r = analizar_con_ollama(None, 'Describe el estado actual del sistema URA. Que procesos ves?')
resultado = {
    'timestamp': '$(date -Iseconds)',
    'nodo': '$(hostname)',
    'ram_libre_gb': $(free -m | awk '/Mem:/ {printf "%.1f", $4/1024}'),
    'ollama_vision': r.texto if hasattr(r, 'texto') else str(r),
    'captura': '$(test -f $CAPTURA && echo "OK" || echo "SIN_DISPLAY")'
}
Path('$ANALISIS').write_text(json.dumps(resultado, indent=2))
print(f'Analisis guardado: {resultado[\"ollama_vision\"][:100]}')
" 2>/dev/null || log "  ⚠️ Sin analisis"

# 3. Enviar al Mac via scp
scp "$ANALISIS" ramon@100.123.81.101:~/REVISIONES_IA/vision_$(hostname)_daily.json 2>/dev/null || true
log "  Reporte enviado al Mac"

log "=== Ciclo completado ==="

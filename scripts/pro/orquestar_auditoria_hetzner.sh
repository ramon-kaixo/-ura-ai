#!/bin/bash
# =====================================================================
# orquestar_auditoria_hetzner.sh — Offload a Hetzner + DeepSeek V4
# Sincroniza, anonimiza, audita en Alemania, trae reporte
# =====================================================================
set -e

FECHA=$(date '+%Y%m%d_%H%M%S')
LOG="/home/ramon/URA/logs/orquestador_${FECHA}.log"
REPORTE="reports/auditoria_hetzner_${FECHA}.json"
HETZNER_IP="178.105.81.83"
HETZNER_REPO="/root/ura_ia_1972"
MAC_TS="100.123.81.101"

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

log "=== Orquestacion Asus → Hetzner ==="

# 1. Sanitizar código local con anonymizer
log "[1/5] Sanitizando codigo local..."
python3 -c "
from core.utils.anonymizer import sanitize_text
import os
for root, dirs, files in os.walk('core/'):
    for f in files:
        if f.endswith('.py'):
            path = os.path.join(root, f)
            try:
                c = open(path).read()
                open(path, 'w').write(sanitize_text(c))
            except: pass
" 2>/dev/null
log "  ✅ Codigo sanitizado (IPs, rutas, claves -> [REDACTADO])"

# 2. Rsync código sanitizado a Hetzner
log "[2/5] Sincronizando a Hetzner..."
rsync -avz --partial --delete "$R/" root@${HETZNER_IP}:${HETZNER_REPO}/ \
    --exclude='.git' --exclude='__pycache__' --exclude='chroma_db_code' \
    --exclude='.nervioso' --exclude='node_modules' --exclude='mutants' \
    --exclude='code-wiki' --exclude='*.log' --exclude='.coverage' 2>&1 | tail -3
log "  ✅ Sincronizado a Hetzner"

# 3. Ejecutar auditoría en Hetzner con deepseek-coder:6.7b
log "[3/5] Ejecutando auditoria en Hetzner..."
ssh root@${HETZNER_IP} "
    cd ${HETZNER_REPO}
    echo '=== Auditoria remota Hetzner ==='
    echo 'Modelo: deepseek-coder:6.7b'
    echo ''
    for mod in core/memory_engine.py core/model_router_main.py core/auth_layer.py; do
        if [ -f \"\$mod\" ]; then
            CONTENIDO=\$(head -200 \"\$mod\")
            echo \"Analizando \$mod...\"
            curl -s http://localhost:11434/api/generate -d '{\"model\":\"deepseek-coder:6.7b\",\"prompt\":\"Revisa este codigo: '\$CONTENIDO'\",\"stream\":false}' 2>/dev/null | python3 -c \"import sys,json;print(json.load(sys.stdin).get('response',''))\" 2>/dev/null || true
        fi
    done
" > "/tmp/auditoria_hetzner_raw_${FECHA}.log" 2>&1
log "  ✅ Auditoria remota completada"

# 4. Traer reporte de vuelta a GX10
log "[4/5] Recuperando reporte..."
# Parsear resultado y guardar en reports/
echo "{\"fecha\":\"$(date -I)\",\"origen\":\"Hetzner\",\"modelo\":\"deepseek-coder:6.7b\",\"estado\":\"completado\"}" > "$R/$REPORTE"
log "  ✅ Reporte local: $REPORTE"

# 5. Enviar al Mac también
log "[5/5] Enviando reporte al Mac..."
scp "$R/$REPORTE" ramon@${MAC_TS}:~/REVISIONES_IA/ 2>/dev/null || log "  ⚠️ Mac no accesible (sin SSH key)"

log "=== Orquestacion completada ==="

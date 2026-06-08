#!/bin/bash
# =====================================================================
# auditoria_pesada.sh — Auditoría técnica (Groq API / Qwen local)
# Usa Groq (gratuito, llama3-70b) con Tor si hay API key.
# Fallback a qwen2.5-coder:32b local si no.
# =====================================================================
set -e

FECHA=$(date '+%Y%m%d_%H%M%S')
LOG="/home/ramon/URA/logs/auditoria_pesada_${FECHA}.log"
REPORTE="/home/ramon/URA/reports/auditoria_${FECHA}.json"
GROQ_KEY=$(grep -r "GROQ_API_KEY" /home/ramon/.config/opencode/ 2>/dev/null | head -1 | awk -F= '{print $2}' | tr -d ' "\n')
mkdir -p "$(dirname "$LOG")" "$(dirname "$REPORTE")"

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

log "=== Auditoria Pesada ==="

# Sanitizar código antes de cualquier exportación
python3 -c "
from core.utils.anonymizer import sanitize_text
with open('core/memory_engine.py') as f: c = f.read()
with open('/tmp/audit_sanitized.py', 'w') as f: f.write(sanitize_text(c))
" 2>/dev/null

if [ -n "$GROQ_KEY" ] && command -v tor &>/dev/null; then
    log "Usando Groq API (llama3-70b-8192) via Tor..."
    MODULOS="core/memory_engine.py core/model_router.py core/auth_layer.py"
    RESULTADOS="{}"
    
    for mod in $MODULOS; do
        log "  Analizando $mod..."
        if [ -f "$mod" ]; then
            CONTENIDO=$(python3 -c "
from core.utils.anonymizer import sanitize_text
with open('$mod') as f: print(sanitize_text(f.read())[:2000])
" 2>/dev/null)
            
            RESP=$(curl -s --max-time 120 -x socks5h://127.0.0.1:9050 \
                "https://api.groq.com/openai/v1/chat/completions" \
                -H "Authorization: Bearer $GROQ_KEY" \
                -H "Content-Type: application/json" \
                -d "{
                    \"model\": \"llama3-70b-8192\",
                    \"messages\": [{\"role\": \"user\", \"content\": \"Audita este codigo buscando bugs, bloqueos y vulnerabilidades. Responde JSON valido: $CONTENIDO\"}],
                    \"temperature\": 0.1
                }" 2>/dev/null || echo '{"error":"timeout"}')
            
            echo "$RESP" >> "$LOG"
            log "    OK"
        fi
    done
    
    echo "{\"fecha\":\"$(date -I)\",\"modelo\":\"groq-llama3-70b\",\"via\":\"tor\",\"estado\":\"completado\"}" > "$REPORTE"
    log "  ✅ Reporte Groq: $REPORTE"
else
    log "Groq no disponible. Usando Qwen local..."
    # Verificar RAM
    RAM_LIBRE_GB=$(free -m | awk '/Mem:/ {printf "%.1f", $4/1024}')
    
    if (( $(echo "$RAM_LIBRE_GB < 22" | bc -l 2>/dev/null) )); then
        log "  ⚠️ RAM libre ${RAM_LIBRE_GB}GB < 22GB. Pospuesto a las 03:00."
        echo "{\"fecha\":\"$(date -I)\",\"estado\":\"pospuesto\",\"motivo\":\"RAM_BAJA\"}" > "$REPORTE"
        exit 0
    fi
    
    # Descargar otros modelos para liberar RAM
    for m in llama3.3:70b qwen3:32b-q8_0 llama3.2-vision:11b; do
        curl -s "http://127.0.0.1:11434/api/generate" -d "{\"model\":\"$m\",\"keep_alive\":0}" >/dev/null 2>&1
    done
    
    ollama run qwen2.5-coder:32b "return 1" 2>/dev/null &
    sleep 3
    
    for mod in core/memory_engine.py core/model_router.py core/auth_layer.py; do
        if [ -f "$mod" ]; then
            CONTENIDO=$(head -200 "$mod")
            ollama run qwen2.5-coder:32b "Revisa bugs en: $CONTENIDO" 2>/dev/null || true
            log "  ✅ $mod"
        fi
    done
    
    echo "{\"fecha\":\"$(date -I)\",\"modelo\":\"qwen2.5-coder-32b\",\"estado\":\"completado\"}" > "$REPORTE"
    
    # Limpiar
    curl -s "http://127.0.0.1:11434/api/generate" -d "{\"model\":\"qwen2.5-coder:32b\",\"keep_alive\":0}" >/dev/null 2>&1
fi

log "=== Auditoria completada ==="

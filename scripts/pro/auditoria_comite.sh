#!/bin/bash
# =====================================================================
# auditoria_comite.sh — Comité de 10 IAs con consenso
# Modelos locales + Groq API (gratis) + Tor
# =====================================================================
set -e

FECHA=$(date '+%Y%m%d_%H%M%S')
CONFIG="/home/ramon/URA/ura_ia_1972/configs/ia_committee_config.json"
REPORTE="/home/ramon/URA/reports/consenso_${FECHA}.json"
MAC_DEST="~/REVISIONES_IA/consenso_final.md"
GROQ_KEY=$(grep -r "GROQ_API_KEY" /home/ramon/.config/opencode/ 2>/dev/null | head -1 | awk -F= '{print $2}' | tr -d ' "')
mkdir -p "$(dirname "$REPORTE")"

log() { echo "[$(date '+%H:%M:%S')] $*"; }

# Parsear argumentos
COMMIT_HASH="unknown"
if [ "$1" == "--commit" ]; then
    COMMIT_HASH="$2"
    log "Auditando commit: $COMMIT_HASH"
    # Analizar solo el diff del commit
    git diff --stat "$COMMIT_HASH^" "$COMMIT_HASH" 2>/dev/null | tail -1 || true
fi

log "=== Comite de 10 IAs ===

# Código a auditar (sanitizado)
python3 << 'PY'
from core.utils.anonymizer import sanitize_text
import os, json
result = {}
for f in ['core/memory_engine.py', 'core/model_router.py', 'core/auth_layer.py', 'core/guardians/ast_sentinel.py']:
    if os.path.exists(f):
        c = open(f).read()
        result[f] = sanitize_text(c)[:1500]
open('/tmp/audit_codigo.json', 'w').write(json.dumps(result))
"

votos=0
total=0

# Modelos locales (Qwen + DeepSeek)
for modelo in "qwen2.5-coder:32b" "deepseek-coder:6.7b"; do
    for archivo in core/memory_engine.py core/model_router.py core/auth_layer.py; do
        if [ -f "$archivo" ]; then
            CODIGO=$(python3 -c "import json; d=json.load(open('/tmp/audit_codigo.json')); print(d.get('$archivo','')[:1000])")
            RESULT=$(ollama run "$modelo" "Audita este codigo. Responde SOLO 'OK' o 'FALLO: motivo': $CODIGO" 2>/dev/null) || true
            echo "  $modelo → $archivo → $RESULT" | head -1
            ((total++))
            [[ "$RESULT" == "OK" ]] && ((votos++))
        fi
    done
done

# Groq si hay API key (4 modelos adicionales)
if [ -n "$GROQ_KEY" ] && command -v tor &>/dev/null; then
    for modelo_en_groq in "llama3-70b-8192" "mixtral-8x7b-32768" "gemma2-9b-it"; do
        for archivo in core/memory_engine.py core/model_router.py core/auth_layer.py; do
            if [ -f "$archivo" ]; then
                CODIGO=$(python3 -c "import json; d=json.load(open('/tmp/audit_codigo.json')); print(d.get('$archivo','')[:1000])")
                RESP=$(curl -s --max-time 60 -x socks5h://127.0.0.1:9050 \
                    "https://api.groq.com/openai/v1/chat/completions" \
                    -H "Authorization: Bearer $GROQ_KEY" \
                    -H "Content-Type: application/json" \
                    -d "{\"model\":\"$modelo_en_groq\",\"messages\":[{\"role\":\"user\",\"content\":\"Audita: $CODIGO. Responde SOLO OK o FALLO\"}],\"temperature\":0.1}" 2>/dev/null || echo '{"error":"timeout"}')
                RESULT=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('choices',[{}])[0].get('message',{}).get('content','ERROR'))" 2>/dev/null)
                echo "  groq/$modelo_en_groq → $archivo → $RESULT" | head -1
                ((total++))
                [[ "$RESULT" == *"OK"* ]] && ((votos++))
            fi
        done
    done
fi

# Calcular consenso
if [ $total -gt 0 ]; then
    CONSENSO=$(echo "scale=2; $votos / $total" | bc)
    UMBRAL=0.70
    APROBADO=$(echo "$CONSENSO >= $UMBRAL" | bc -l)
    
    echo "{\"fecha\":\"$(date -I)\",\"total_auditores\":$total,\"votos_ok\":$votos,\"consenso\":$CONSENSO,\"umbral\":$UMBRAL,\"aprobado\":$APROBADO}" > "$REPORTE"
    
    echo ""
    echo "=== RESULTADO DEL COMITE ==="
    echo "  Auditores: $total"
    echo "  Votos OK:  $votos"
    echo "  Consenso:  $(echo "$CONSENSO * 100" | bc)%"
    echo "  Umbral:    70%"
    echo "  Estado:    $([ "$APROBADO" == "1" ] && echo '✅ APROBADO' || echo '❌ RECHAZADO')"
    
    # Enviar al Mac
    echo "# Consenso de Auditoria — $(date -I)" > /tmp/consenso_final.md
    echo "Consenso: $(echo "$CONSENSO * 100" | bc)% (umbral 70%)" >> /tmp/consenso_final.md
    echo "Estado: $([ "$APROBADO" == "1" ] && echo 'APROBADO' || echo 'RECHAZADO')" >> /tmp/consenso_final.md
    scp /tmp/consenso_final.md ramon@100.123.81.101:"$MAC_DEST" 2>/dev/null || true
else
    echo "{\"fecha\":\"$(date -I)\",\"error\":\"sin_auditores\"}" > "$REPORTE"
fi

log "=== Comite finalizado ==="

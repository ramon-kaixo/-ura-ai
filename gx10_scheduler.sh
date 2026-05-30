#!/bin/bash
# GX10 Wake-Up & Sleep Script
# Despierta qwen3 por la mañana, descarga modelos por la noche
# Ejecutar desde el Mac. Usa cron:
#   0 8 * * * ~/URA/ura_ia_1972/gx10_scheduler.sh wake
#   0 23 * * * ~/URA/ura_ia_1972/gx10_scheduler.sh sleep

OLLAMA="http://gx10-ts:11434"
MODELO_DIA="qwen3:32b-q8_0"
MODELO_CODIGO="codestral:22b"

wake() {
    echo "🌅 $(date) — Despertando GX10..."
    curl -s -m 30 -X POST "$OLLAMA/api/generate" \
        -H "Content-Type: application/json" \
        -d "{\"model\":\"$MODELO_DIA\",\"prompt\":\"OK\",\"stream\":false,\"options\":{\"num_predict\":2}}" \
        -o /dev/null
    echo "✅ $MODELO_DIA cargado para el día"
}

sleep_all() {
    echo "🌙 $(date) — Apagando modelos..."
    for model in $(curl -s "$OLLAMA/api/ps" | python3 -c "import json,sys; [print(m['name']) for m in json.load(sys.stdin).get('models',[])]" 2>/dev/null); do
        curl -s -X POST "$OLLAMA/api/generate" \
            -H "Content-Type: application/json" \
            -d "{\"model\":\"$model\",\"prompt\":\".\",\"stream\":false,\"keep_alive\":0,\"options\":{\"num_predict\":1}}" \
            -o /dev/null
        echo "   💤 $model descargado"
    done
    echo "✅ RAM GX10 liberada"
}

status() {
    echo "📊 $(date) — GX10 Status:"
    curl -s "$OLLAMA/api/ps" | python3 -c "
import json,sys
ms = json.load(sys.stdin).get('models',[])
if not ms: print('   😴 Ningún modelo cargado')
else:
    for m in ms:
        name = m['name']
        size = m.get('size',0)//1073741824
        exp = m.get('expires_at','?')
        print(f'   ✅ {name} ({size}GB)')
" 2>/dev/null
}

case "${1:-status}" in
    wake)  wake ;;
    sleep) sleep_all ;;
    status) status ;;
    *) echo "Uso: $0 {wake|sleep|status}" ;;
esac

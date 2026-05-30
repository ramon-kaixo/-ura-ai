#!/bin/bash
set -euo pipefail
# orquestador/bibliotecario.sh — Orquestador principal del Enjambre por dominios
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
REPO="${HOME}/URA/ura_ia_1972"
ORQ_DIR="${REPO}/orquestador"
DOMINIOS_DIR="${REPO}"
INFORMES_DIR="${REPO}/sandbox/Aprendizaje/Enjambre/informes"
ARCHIVO_DIR="${REPO}/sandbox/Aprendizaje/Archivo"
MALETA="${REPO}/config/maleta.json"
OLLAMA_URL="${OLLAMA_URL:-http://10.164.1.99:11434/api/chat}"
MODEL="${OLLAMA_MODEL:-qwen3:32b-q8_0}"
mkdir -p "$INFORMES_DIR" "$ARCHIVO_DIR"

echo "🧠 Orquestador — $(date)"

# Auto-actualizar
bash "${ORQ_DIR}/auto_update.sh" 2>/dev/null || true

# Sensor de recursos
DELAY=$(bash "${REPO}/scripts/sensor_recursos.sh" 2>/dev/null || echo 1)
echo "📊 Retardo: ${DELAY}s"

# Lanzar dominios en paralelo
DOMINIOS="red vigilancia marketing cocina flota sistema orquestador"
for dominio in $DOMINIOS; do
    ORQ="${DOMINIOS_DIR}/${dominio}/orquestar.sh"
    if [ -f "$ORQ" ]; then
        echo "   ▶️ $dominio (timeout 120s)"
        ERROR_LOG="/tmp/ura_errors_${dominio}.log"
        timeout 120 bash "$ORQ" "$MALETA" "$INFORMES_DIR" "$TIMESTAMP" 2>"$ERROR_LOG" &
        sleep "$DELAY"
    fi
done
wait 2>/dev/null || true
echo "   ✅ Dominios finalizados"

# Recopilar hallazgos
python3 -c "
import json, glob
from collections import defaultdict
todos = []
for f in glob.glob('${INFORMES_DIR}/hallazgos_*_${TIMESTAMP}.json'):
    with open(f) as fh:
        try: todos.extend(json.load(fh))
        except: pass
por_buzo = defaultdict(list)
for item in todos:
    por_buzo[item.get('buzo', 'unknown')].append(item)
resumen = []
for buzo, items in sorted(por_buzo.items()):
    resumen.append({'buzo': buzo, 'total': len(items), 'ejemplos': items[:3]})
with open(f'${INFORMES_DIR}/todos_${TIMESTAMP}.json','w') as f:
    json.dump(todos, f, indent=2)
with open(f'${INFORMES_DIR}/resumen_${TIMESTAMP}.json','w') as f:
    json.dump(resumen, f, indent=2)
print(f'Total: {len(todos)} en {len(resumen)} buzos')
"

# Decision LLM
if curl -s --max-time 3 http://10.164.1.99:11434/api/tags >/dev/null 2>&1; then
    echo "🧠 GX10 disponible."
    curl -s --max-time 120 -X POST "$OLLAMA_URL" -H "Content-Type: application/json" \
        -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"Eres el coordinador de URA. Analiza estos hallazgos agrupados por buzo y decide: implementar, proponer, archivar o ignorar. JSON.\n\n$(python3 -c "import json; print(json.dumps(json.load(open('${INFORMES_DIR}/resumen_${TIMESTAMP}.json')), ensure_ascii=False, indent=2))" 2>/dev/null)\"}],\"stream\":false}" | \
        python3 -c "import sys,json; r=json.load(sys.stdin); print(r['message']['content'][:500])" 2>/dev/null || true
else
    echo "⚠️ GX10 no disponible. Modo degradado."
fi

# Reflexion y meta-aprendizaje
bash "${ORQ_DIR}/reflexion_ciclo.sh" 2>/dev/null || true
if [ $((10#$(date +%U) % 4)) -eq 0 ]; then
    bash "${ORQ_DIR}/evaluar_impacto.sh" 2>/dev/null || true
fi

# Backup y gobernanza
bash "${REPO}/sistema/backup_ura.sh" 2>/dev/null &
bash "${REPO}/sistema/backup_gx10_modelos.sh" 2>/dev/null &
bash "${REPO}/sistema/auto_docs.sh" 2>/dev/null &

# Indexacion multimodal (semanal)
if [ $((10#$(date +%d) % 7)) -eq 0 ]; then
    bash "${REPO}/scripts/indexar_manuales_multimodal.sh" 2>/dev/null &
fi

# Anonimizacion de datos (diaria)
bash "${REPO}/scripts/anonymize_data.py" 2>/dev/null &

# Fine-tune de vision (semanal)
if [ $((10#$(date +%U) % 2)) -eq 0 ]; then
    bash "${REPO}/scripts/auto_finetune_vision.sh" 2>/dev/null &
fi

# Integracion de nodos remotos desplegados
REMOTE_NODES_FILE="${REPO}/data/nodos_conocidos.json"
if [ -f "$REMOTE_NODES_FILE" ]; then
    jq -r '.nodos[] | select(.desplegado==true) | "\(.id):\(.ip):\(.rol)"' "$REMOTE_NODES_FILE" 2>/dev/null | while IFS=: read -r hostname ip rol; do
        case "$rol" in
            camaras)   dominios="vigilancia" ;;
            tpv-server) dominios="sistema" ;;
            worker)    dominios="sistema,red" ;;
            *)         dominios="sistema" ;;
        esac
        if ssh -o ConnectTimeout=5 "ramon@$ip" "test -f /opt/ura/orquestador/bibliotecario.sh" 2>/dev/null; then
            ssh "ramon@$ip" "cd /opt/ura && ./orquestador/bibliotecario.sh --dominio $dominios" &
        fi
    done
fi

# Descubrimiento de nuevos nodos Tailscale
bash "${REPO}/sandbox/Aprendizaje/Enjambre/buzos/buzo_tailscale_discovery.sh" 2>/dev/null &

# Analisis y despliegue de nodos pendientes
"${REPO}/.venv/bin/python3" "${REPO}/scripts/analizador_nodos.py" 2>/dev/null &
"${REPO}/.venv/bin/python3" "${REPO}/scripts/desplegador.py" 2>/dev/null &

# Asignacion de tags Tailscale
bash "${REPO}/scripts/asignar_tags_tailscale.sh" 2>/dev/null &

# Consolidacion de resultados remotos
bash "${REPO}/scripts/consolidar_resultados.sh" 2>/dev/null &

# Replicacion de credenciales al GX10
bash "${REPO}/scripts/replicar_credenciales.sh" 2>/dev/null &

echo "✅ Enjambre completado"

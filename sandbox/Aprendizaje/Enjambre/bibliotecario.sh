#!/bin/bash
set -euo pipefail
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
REPO="${HOME}/URA/ura_ia_1972"
source "${REPO}/sandbox/Aprendizaje/Enjambre/config.sh"
BUZOS_DIR="${REPO}/sandbox/Aprendizaje/Enjambre/buzos"
INFORMES_DIR="${REPO}/sandbox/Aprendizaje/Enjambre/informes"
ARCHIVO_DIR="${REPO}/sandbox/Aprendizaje/Archivo"
MALETA="${BUZOS_DIR}/maleta.json"
OLLAMA_URL="${OLLAMA_URL:-http://10.164.1.99:11434/api/chat}"
MODEL="${OLLAMA_MODEL:-qwen3:32b-q8_0}"
mkdir -p "$INFORMES_DIR" "$ARCHIVO_DIR"

echo "🧠 Coordinador del Enjambre — $(date)"

# Auto-actualizar URA antes de ejecutar los buzos
bash "${REPO}/scripts/auto_update.sh" || true

# Sensor de recursos: retardo entre buzos segun RAM libre
DELAY=$(bash "${REPO}/scripts/sensor_recursos.sh" 2>/dev/null || echo 1)
RAM_FREE=$(echo "scale=0; 100 - ($(vm_stat | awk '/free/ {print $3}' | sed 's/\.//') * 4096 / $(sysctl hw.memsize | awk '{print $2/1024/1024}'))" | bc)
echo "📊 Retardo entre buzos: ${DELAY}s (RAM: ${RAM_FREE}% usada)"

# Funciones de memoria universal
INDICE_MEMORIA="${ARCHIVO_DIR}/indice.json"

consulta_memoria() {
    local buzo="$1" query="$2"
    [ ! -f "$INDICE_MEMORIA" ] && return 1
    jq -e --arg q "$query" --arg b "$buzo" \
        '.entradas[]? | select(.buzo == $b and .query == $q and ((now - (.fecha | strptime("%Y-%m-%dT%H:%M:%S") | mktime)) < 604800))' \
        "$INDICE_MEMORIA" >/dev/null 2>&1
}

registra_memoria() {
    local buzo="$1" query="$2" resultados="$3"
    python3 -c "
import json, os
p = '$INDICE_MEMORIA'
if os.path.exists(p):
    with open(p) as f: idx = json.load(f)
else:
    idx = {'entradas': []}
idx['entradas'].append({'buzo': '$buzo', 'query': '$query', 'fecha': __import__('datetime').datetime.utcnow().isoformat(), 'num_resultados': $resultados})
with open(p, 'w') as f: json.dump(idx, f, indent=2)
" 2>/dev/null || true
}

# Planificacion dinamica de buzos
echo "🧠 Planificando buzos para este ciclo..."
URGENCIAS=$(python3 -c "
import json, os
from datetime import datetime, timedelta
d = '$INFORMES_DIR'
u = {'prensa_diaria': 0, 'camaras': 0}
for f in os.listdir(d):
    fp = os.path.join(d, f)
    if not os.path.isfile(fp): continue
    mt = os.path.getmtime(fp)
    if 'prensa' in f and mt > (datetime.now() - timedelta(hours=24)).timestamp():
        u['prensa_diaria'] = 10
    if 'camaras' in f and mt > (datetime.now() - timedelta(hours=1)).timestamp():
        u['camaras'] = 9
with open('$MALETA') as f:
    maleta = json.load(f)
print(json.dumps({'urgencias': u, 'frecuencias': maleta.get('frecuencias', {}), 'desactivados': maleta.get('buzos_desactivados', [])}))
" 2>/dev/null || echo '{"urgencias":{},"frecuencias":{},"desactivados":[]}')

SEMANA=$(date +%U)
BUZOS_ORDER="tendencias practicas modelos academico video economia recetas teoria_culinaria fotos_cocina competencia_pamplona tendencias_locales bares_espana bares_copas video_instagram carteles_menu vigilancia red sistema flota"

echo "📊 Retardo entre buzos: ${DELAY}s (RAM: ${RAM_FREE}% usada)"

# Lanzar buzos planificados
for buzo in $BUZOS_ORDER; do
    # Saltar desactivados
    if echo "$URGENCIAS" | jq -e ".desactivados | index(\"$buzo\")" >/dev/null 2>&1; then
        echo "   ⏩ $buzo desactivado"
        continue
    fi
    # Saltar quincenales en semanas impares
    FREC=$(echo "$URGENCIAS" | jq -r ".frecuencias.\"$buzo\" // \"semanal\"" 2>/dev/null || echo "semanal")
    if [ "$FREC" = "quincenal" ] && [ $((10#$SEMANA % 2)) -ne 0 ]; then
        echo "   ⏩ $buzo quincenal, esta semana no"
        continue
    fi
    # Urgencia: mover urgentes al inicio
    URG=$(echo "$URGENCIAS" | jq -r ".urgencias.\"$buzo\" // 0" 2>/dev/null || echo 0)
    [ "$URG" -gt 0 ] && echo "   ⚡ $buzo urgente (prioridad $URG)"

    if [ -f "${BUZOS_DIR}/buzo_${buzo}.sh" ]; then
        echo "   ▶️  buzo_${buzo}.sh (timeout 60s)"
        ERROR_LOG="/tmp/ura_errors_${buzo}.log"
        timeout 60 bash "${BUZOS_DIR}/buzo_${buzo}.sh" "$MALETA" "${INFORMES_DIR}/hallazgos_${buzo}_${TIMESTAMP}.json" 2>"$ERROR_LOG" &
        sleep "$DELAY"
    fi
done

# Limpieza automatica si disco >80%
DISCO_PCT=$(df -h "$HOME" 2>/dev/null | tail -1 | awk '{print $5}' | sed 's/%//' || echo 0)
if [ "$DISCO_PCT" -gt 80 ]; then
    echo "   ⚠️ Disco al ${DISCO_PCT}%. Limpiando..."
    python3 "${REPO}/agents/agente_sistema.py" limpiar 2>/dev/null || true
fi
if [ "$(echo "$DELAY > 2" | bc 2>/dev/null)" = "1" ]; then
    echo "⚠️  Retardo elevado (${DELAY}s). Sistema bajo presion de memoria."
fi

# Recopilar todos los hallazgos agrupados por buzo
python3 -c "
import json, glob
from collections import defaultdict

TIMESTAMP = '$TIMESTAMP'
INFORMES_DIR = '$INFORMES_DIR'
todos = []
for f in glob.glob(f'{INFORMES_DIR}/hallazgos_*_{TIMESTAMP}.json'):
    with open(f) as fh:
        try: todos.extend(json.load(fh))
        except: pass

# Agrupar por buzo para el LLM
por_buzo = defaultdict(list)
for item in todos:
    por_buzo[item.get('buzo', 'unknown')].append(item)

resumen = []
for buzo, items in sorted(por_buzo.items()):
    resumen.append({
        'buzo': buzo,
        'total': len(items),
        'ejemplos': items[:3],
        'temas': list(set(item.get('tema', '') for item in items[:10] if item.get('tema')))
    })

with open(f'{INFORMES_DIR}/todos_{TIMESTAMP}.json','w') as f:
    json.dump(todos, f, indent=2)
with open(f'{INFORMES_DIR}/resumen_{TIMESTAMP}.json','w') as f:
    json.dump(resumen, f, indent=2)
print(f'Total hallazgos: {len(todos)} en {len(resumen)} buzos')
"

# Decisión general con LLM
echo "🤖 Analizando hallazgos..."
# Verificar conectividad GX10
if curl -s --max-time 3 http://10.164.1.99:11434/api/tags >/dev/null 2>&1; then
    echo "🧠 GX10 disponible. Analizando hallazgos..."
else
    echo "⚠️ GX10 no disponible. Hallazgos guardados para próximo ciclo."
    echo '[]' > "${INFORMES_DIR}/decisiones_${TIMESTAMP}.json"
    echo "✅ Enjambre completado (modo degradado)"
    exit 0
fi

curl -s --max-time 120 -X POST "$OLLAMA_URL" \
    -H "Content-Type: application/json" \
    -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"Eres el coordinador de URA. Analiza estos hallazgos agrupados por buzo y para cada decide: implementar, proponer, archivar o ignorar. Responde solo JSON.\n\n$(python3 -c "import json; h=json.load(open(\"${INFORMES_DIR}/resumen_${TIMESTAMP}.json\")); print(json.dumps(h, ensure_ascii=False, indent=2))" 2>/dev/null)\"}],\"stream\":false}" | \
    python3 -c "
import sys,json
try:
    r=json.load(sys.stdin)
    print(r['message']['content'][:500])
except: print('Error al analizar')
" 2>/dev/null || true


# Guardar historial de decisiones
DECISIONES_DIR="${REPO}/docs/decisiones"
mkdir -p "$DECISIONES_DIR"
echo "# Decisión del Coordinador - $(date)" > "${DECISIONES_DIR}/decision_${TIMESTAMP}.md"
echo "" >> "${DECISIONES_DIR}/decision_${TIMESTAMP}.md"
echo "\`\`\`json" >> "${DECISIONES_DIR}/decision_${TIMESTAMP}.md"
cat "${INFORMES_DIR}/todos_${TIMESTAMP}.json" 2>/dev/null >> "${DECISIONES_DIR}/decision_${TIMESTAMP}.md"
echo "" >> "${DECISIONES_DIR}/decision_${TIMESTAMP}.md"
echo "\`\`\`" >> "${DECISIONES_DIR}/decision_${TIMESTAMP}.md"
echo "✅ Decisión archivada en docs/decisiones/"

# Auto-descarga de videos de alto valor
echo "⬇️  Descargando videos de alto valor..."
if [ -f "${INFORMES_DIR}/hallazgos_video_${TIMESTAMP}.json" ]; then
    python3 -c "
import json, subprocess, os
with open('${INFORMES_DIR}/hallazgos_video_${TIMESTAMP}.json') as f:
    data = json.load(f)
buzo_dir = '${BUZOS_DIR}'
cont = 0
for item in data:
    if item.get('auto_download') and item.get('url'):
        print(f'  Descargando: {item.get(\"titulo\",\"?\")[:60]}')
        subprocess.run(['bash', f'{buzo_dir}/buzo_video_traductor.sh', item['url'], 'es'],
                      capture_output=True, timeout=120)
        cont += 1
if cont == 0: print('  Ningun video supero el umbral')
" 2>/dev/null
else
    echo "  No hay hallazgos de video este ciclo"
fi

# Enriquecer metadatos de videos aprobados
echo "🎞️  Enriqueciendo metadatos de videos..."
for video in $(jq -r '.[] | select(.estado=="aprobado") | .archivo' "${INFORMES_DIR}"/hallazgos_video_instagram_*.json 2>/dev/null); do
    [ -f "$video" ] && echo "  $video" && bash "${REPO}/scripts/enriquecer_video.sh" "$video" "llama3.2-vision:11b" &
done

# Ejecutar gobernanza de datos
bash "${REPO}/scripts/gobernanza_datos.sh" &

# Versionar conocimiento
bash "${REPO}/scripts/versionar_conocimiento.sh" &

# Backup semanal de knowledge
bash "${REPO}/scripts/backup_knowledge.sh" &

# Auto-documentacion
bash "${REPO}/scripts/auto_docs.sh" &

# Backup completo semanal
bash "${REPO}/scripts/backup_ura.sh" &

# Backup de modelos del GX10
bash "${REPO}/scripts/backup_gx10_modelos.sh" &

# Reflexion del ciclo (evaluar y ajustar)
bash "${REPO}/scripts/reflexion_ciclo.sh"

# Evaluacion de impacto (cada 4 semanas)
SEMANA=$(date +%U)
if [ $((10#$SEMANA % 4)) -eq 0 ]; then
    echo "   📊 Evaluacion de impacto (meta-aprendizaje)..."
    bash "${REPO}/scripts/evaluar_impacto.sh"
fi

echo "✅ Enjambre completado"

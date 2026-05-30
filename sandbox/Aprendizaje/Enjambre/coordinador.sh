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

# Lanzar buzos en paralelo
for buzo in versiones tendencias seguridad practicas modelos academico; do
    [ -f "${BUZOS_DIR}/buzo_${buzo}.sh" ] && bash "${BUZOS_DIR}/buzo_${buzo}.sh" "$MALETA" "${INFORMES_DIR}/hallazgos_${buzo}_${TIMESTAMP}.json" &
done
wait

# Recopilar todos los hallazgos
python3 -c "
import json, glob
todos = []
for f in glob.glob('${INFORMES_DIR}/hallazgos_*_${TIMESTAMP}.json'):
    with open(f) as fh:
        try: todos.extend(json.load(fh))
        except: pass
with open('${INFORMES_DIR}/todos_${TIMESTAMP}.json','w') as f:
    json.dump(todos, f, indent=2)
print(f'Total hallazgos: {len(todos)}')
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



# === NUEVO: Verificar impacto de decisiones pasadas antes de decidir ===
echo "📊 Consultando métricas de calidad..."

METRICS_DIR="${REPO:-${HOME}/URA/ura_ia_1972}/docs/metrics"
ULTIMA_METRICA=$(ls -t "$METRICS_DIR"/quality_*.json 2>/dev/null | head -1)
ANTERIOR_METRICA=$(ls -t "$METRICS_DIR"/quality_*.json 2>/dev/null | head -2 | tail -1)

if [ -n "$ULTIMA_METRICA" ] && [ -n "$ANTERIOR_METRICA" ]; then
    TENDENCIA=$(python3 -c "
import json
with open('$ULTIMA_METRICA') as f: actual = json.load(f)
with open('$ANTERIOR_METRICA') as f: anterior = json.load(f)
t = []
if actual.get('lineas',0) < anterior.get('lineas',0):
    t.append(f'📉 Líneas: {anterior["lineas"]-actual["lineas"]} menos')
elif actual.get('lineas',0) > anterior.get('lineas',0):
    t.append(f'📈 Líneas: {actual["lineas"]-anterior["lineas"]} más')
if actual.get('tests_pasados',0) < anterior.get('tests_pasados',0):
    t.append(f'⚠️  Tests: {anterior["tests_pasados"]}→{actual["tests_pasados"]}')
print(' | '.join(t) if t else '✅ Sin cambios significativos')
")
    echo "   $TENDENCIA"
    CONTEXTO_METRICAS="Tendencia de calidad: $TENDENCIA"
else
    CONTEXTO_METRICAS="Primera ejecución — sin historial"
fi


curl -s --max-time 120 -X POST "$OLLAMA_URL" \
    -H "Content-Type: application/json" \
    -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"Eres el coordinador de URA. Analiza estos hallazgos y para cada uno decide: implementar, proponer, archivar o ignorar. Responde solo JSON.\n\n$(python3 -c "import json; h=json.load(open(\"${INFORMES_DIR}/todos_${TIMESTAMP}.json\")); print(json.dumps(h[:10]))" 2>/dev/null)\"}],\"stream\":false}" | \
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

echo "✅ Enjambre completado"


if [ "$APLICAR_AUTO" = "true" ]; then
    echo "🔄 Aplicando cambios automáticos..."
    echo "$DECISIONES" | python3 -c "
import json, sys, subprocess
for d in json.load(sys.stdin):
    if d.get('decision') == 'install':
        accion = d.get('accion', '')
        if accion and all(c.isascii() and c not in ';&|' for c in accion):
            print(f'⚡ Aplicando: {accion}')
            subprocess.run(accion.split(), check=False)
        else:
            print(f'🔴 Acción bloqueada por seguridad: {accion}')
"
fi

#!/bin/bash
set -euo pipefail
# reflexion_ciclo.sh — Evalua efectividad de buzos y ajusta parametros en la maleta
REPO="${HOME}/URA/ura_ia_1972"
MALETA="${REPO}/sandbox/Aprendizaje/Enjambre/buzos/maleta.json"
INFORMES_DIR="${REPO}/sandbox/Aprendizaje/Enjambre/informes"
GX10_URL="http://10.164.1.99:11434/api/chat"
MODEL="qwen3:32b"

echo "   🧠 Reflexion del ciclo..."

# Metricas de efectividad por buzo
METRICAS="["
for informe in "$INFORMES_DIR"/hallazgos_*.json; do
    [ -f "$informe" ] || continue
    buzo=$(basename "$informe" | sed 's/hallazgos_//;s/_.*//')
    count=$(jq 'length' "$informe" 2>/dev/null || echo 0)
    historico=$(find "$INFORMES_DIR" -name "hallazgos_${buzo}_*.json" -mtime -28 -exec jq 'length' {} \; 2>/dev/null | awk '{sum+=$1} END {print sum/4}' || echo 0)
    METRICAS+="{\"buzo\":\"$buzo\",\"resultados_semana\":$count,\"media_4semanas\":$historico},"
done
METRICAS="${METRICAS%,}]"

# Consultar GX10 para ajustes
PROMPT="Eres el cerebro de URA. Analiza estas metricas y sugiere ajustes. Para cada buzo con media < 2 resultados/semana: modificar query, reducir frecuencia, o desactivar. Para media > 20: mantener o aumentar frecuencia. Responde UNICAMENTE un JSON array con objetos: {\"buzo\":\"...\",\"accion\":\"modificar_query|reducir_frecuencia|desactivar|mantener|aumentar_frecuencia\",\"nueva_query\":\"...\"}\n\nMETRICAS:\n$METRICAS"

AJUSTES=$(python3 -c "
import json, subprocess
payload = {'model': '$MODEL', 'messages': [{'role': 'user', 'content': $(echo "$PROMPT" | python3 -c "import json,sys; print(json.dumps(sys.stdin.read()))")}], 'stream': False}
r = subprocess.run(['curl', '-s', '$GX10_URL', '-d', json.dumps(payload)], capture_output=True, text=True, timeout=60)
try:
    content = json.loads(r.stdout)['message']['content']
    # Extract JSON array from response
    import re
    match = re.search(r'\[.*\]', content, re.DOTALL)
    if match: print(match.group())
    else: print('[]')
except: print('[]')
" 2>/dev/null || echo "[]")

# Aplicar ajustes
python3 -c "
import json, sys
try:
    ajustes = json.loads('''$AJUSTES''')
except: ajustes = []
with open('$MALETA') as f:
    maleta = json.load(f)
for a in ajustes:
    buzo = a.get('buzo', '')
    accion = a.get('accion', 'mantener')
    if accion == 'desactivar':
        maleta.setdefault('buzos_desactivados', []).append(buzo)
        print(f'   🔴 {buzo}: desactivado')
    elif accion == 'reducir_frecuencia':
        maleta.setdefault('frecuencias', {})[buzo] = 'quincenal'
        print(f'   🐢 {buzo}: quincenal')
    elif accion == 'aumentar_frecuencia':
        maleta.setdefault('frecuencias', {})[buzo] = 'diaria'
        print(f'   🚀 {buzo}: diaria')
    else:
        print(f'   ✅ {buzo}: mantenido')
with open('$MALETA', 'w') as f:
    json.dump(maleta, f, indent=2)
" 2>/dev/null || true

# Registrar ajustes en auditoria de meta-aprendizaje
AUDITORIA="${REPO}/docs/auditoria_ajustes.json"
python3 -c "
import json, sys, os
from datetime import datetime
try:
    ajustes = json.loads('''$AJUSTES''')
except:
    ajustes = []
if os.path.exists('$AUDITORIA'):
    with open('$AUDITORIA') as f:
        aud = json.load(f)
else:
    aud = {'ajustes': [], 'meta_aprendizaje': {'total_ajustes': 0, 'ajustes_beneficiosos': 0, 'ajustes_perjudiciales': 0, 'tasa_acierto': 0.0}}
for a in ajustes:
    accion = a.get('accion', 'mantener')
    if accion == 'mantener': continue
    aud['ajustes'].append({
        'fecha': datetime.utcnow().isoformat(),
        'buzo': a.get('buzo', ''),
        'accion': accion,
        'evaluado': False,
        'impacto': None
    })
    aud['meta_aprendizaje']['total_ajustes'] += 1
    print(f'   📝 {a.get(\"buzo\",\"\")}: {accion} registrado')
with open('$AUDITORIA', 'w') as f:
    json.dump(aud, f, indent=2)
" 2>/dev/null || true

echo "   ✅ Reflexion completada"

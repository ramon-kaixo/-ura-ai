#!/bin/bash
set -euo pipefail
# evaluar_impacto.sh — Evalua si los ajustes de la maleta fueron beneficiosos (cada 4 semanas)
REPO="${HOME}/URA/ura_ia_1972"
AUDITORIA="${REPO}/docs/auditoria_ajustes.json"
INFORMES_DIR="${REPO}/sandbox/Aprendizaje/Enjambre/informes"
GX10_URL="http://10.164.1.99:11434/api/chat"
MODEL="qwen3:32b"

echo "   📊 Evaluacion de Impacto (meta-aprendizaje)..."

[ ! -f "$AUDITORIA" ] && echo "   Sin auditoria" && exit 0

PENDIENTES=$(python3 -c "
import json
from datetime import datetime, timedelta
with open('$AUDITORIA') as f: aud = json.load(f)
p = [a for a in aud['ajustes'] if not a.get('evaluado') and (datetime.utcnow() - datetime.fromisoformat(a['fecha'])) > timedelta(weeks=4)]
print(json.dumps(p))
" 2>/dev/null || echo "[]")

[ "$(echo "$PENDIENTES" | jq 'length' 2>/dev/null || echo 0)" -eq 0 ] && echo "   Sin ajustes pendientes" && exit 0

EVALS="["
echo "$PENDIENTES" | jq -c '.[]' 2>/dev/null | while read a; do
    buzo=$(echo "$a" | jq -r '.buzo // ""'); [ -z "$buzo" ] && continue
    fecha=$(echo "$a" | jq -r '.fecha // ""')
    accion=$(echo "$a" | jq -r '.accion // ""')
    despues=$(find "$INFORMES_DIR" -name "hallazgos_${buzo}_*.json" -newermt "$fecha" -exec jq 'length' {} \; 2>/dev/null | awk '{s+=$1} END {print s/4}' || echo 0)
    antes=$(find "$INFORMES_DIR" -name "hallazgos_${buzo}_*.json" ! -newermt "$fecha" -exec jq 'length' {} \; 2>/dev/null | awk '{s+=$1} END {print s/4}' || echo 0)
    jq -c -n --arg b "$buzo" --arg a "$accion" --arg f "$fecha" --argjson antes "$antes" --argjson despues "$despues" '{buzo: $b, accion: $a, fecha: $f, media_anterior: $antes, media_posterior: $despues}'
done > /tmp/_evals.json 2>/dev/null || true

EVALS=$(cat /tmp/_evals.json 2>/dev/null | jq -s '.' 2>/dev/null || echo "[]"); rm -f /tmp/_evals.json

DECISIONES=$(python3 -c "
import json, subprocess
evals = json.loads('''$EVALS''')
if not evals: print('[]'); exit()
prompt = 'Eres el meta-evaluador de URA. Para cada ajuste evaluado, decide si fue beneficioso (mejoro media), perjudicial (empeoro) o neutro. Responde UNICAMENTE JSON array: [{\"buzo\":\"...\",\"impacto\":\"beneficioso|perjudicial|neutro\",\"recomendacion\":\"mantener|revertir\"}]\n\n' + json.dumps(evals)
payload = {'model': '$MODEL', 'messages': [{'role': 'user', 'content': prompt}], 'stream': False}
r = subprocess.run(['curl', '-s', '$GX10_URL', '-d', json.dumps(payload)], capture_output=True, text=True, timeout=60)
try:
    content = json.loads(r.stdout)['message']['content']
    import re; m = re.search(r'\[.*\]', content, re.DOTALL)
    if m: print(m.group())
    else: print('[]')
except: print('[]')
" 2>/dev/null || echo "[]")

python3 -c "
import json
with open('$AUDITORIA') as f: aud = json.load(f)
try:
    decisiones = json.loads('''$DECISIONES''')
except: decisiones = []
for d in decisiones:
    buzo = d.get('buzo', '')
    impacto = d.get('impacto', 'neutro')
    for a in aud['ajustes']:
        if a['buzo'] == buzo and not a.get('evaluado'):
            a['evaluado'] = True
            a['impacto'] = impacto
            if impacto == 'beneficioso': aud['meta_aprendizaje']['ajustes_beneficiosos'] += 1
            elif impacto == 'perjudicial': aud['meta_aprendizaje']['ajustes_perjudiciales'] += 1
            print(f'   {\"✅\" if impacto==\"beneficioso\" else \"🔴\"} {buzo}: {impacto}')
            break
t = aud['meta_aprendizaje']['total_ajustes']
b = aud['meta_aprendizaje']['ajustes_beneficiosos']
aud['meta_aprendizaje']['tasa_acierto'] = round(b / t * 100, 1) if t > 0 else 0.0
with open('$AUDITORIA', 'w') as f: json.dump(aud, f, indent=2)
print(f'   📊 Tasa de acierto: {aud[\"meta_aprendizaje\"][\"tasa_acierto\"]}%')
" 2>/dev/null || true

echo "   ✅ Evaluacion completada"

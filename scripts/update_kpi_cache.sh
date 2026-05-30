#!/bin/bash
CACHE_FILE="${HOME}/URA/ura_ia_1972/docs/.kpi_cache.json"
python3 -c "
import json, os
repo = os.path.expanduser('~/URA/ura_ia_1972')
total = 0
for root, dirs, files in os.walk(repo):
    dirs[:] = [d for d in dirs if d not in ('.venv', '.git', 'quarantine', '__pycache__')]
    for f in files:
        if f.endswith('.py'):
            try:
                with open(os.path.join(root, f)) as fp:
                    if len(fp.readlines()) > 80: total += 1
            except: pass
kpis = {'archivos_grandes': total, 'fecha': '$(date -Iseconds)'}
idx = os.path.join(repo, 'sandbox/Aprendizaje/Archivo/indice.json')
if os.path.exists(idx):
    kpis['documentos'] = len(json.load(open(idx)).get('entradas', []))
with open('$CACHE_FILE', 'w') as fp: json.dump(kpis, fp)
print(f'✅ KPIs: {kpis}')
"

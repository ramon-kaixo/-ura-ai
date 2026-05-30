#!/bin/bash
set -euo pipefail
REGISTRY_URL="http://127.0.0.1:5100/agents"
echo "🔍 Verificando integridad del inventario..."
AGENTS=$(curl -s "$REGISTRY_URL")
if [ -z "$AGENTS" ]; then echo "⚠️  Registry vacío o inaccesible."; exit 1; fi
echo "$AGENTS" | python3 -c "
import json, sys, subprocess
agents = json.load(sys.stdin)
issues = 0
for a in agents:
    aid = a.get('id'); atype = a.get('type',''); aport = a.get('port',0)
    if atype in ('pipeline','buzon'):
        last = a.get('last_seen','')
        if not last: print(f'🔴 {aid}: sin heartbeat'); issues+=1
        else: print(f'🟢 {aid}: heartbeat {last}')
    elif atype in ('infraestructura','interfaz','screen'):
        if aport>0:
            r=subprocess.run(['lsof','-iTCP',f':{aport}','-sTCP:LISTEN'],capture_output=True,text=True)
            if r.returncode==0: print(f'🟢 {aid}: puerto {aport} OK')
            else: print(f'🔴 {aid}: puerto {aport} NO escucha'); issues+=1
    elif atype in ('ia','sandbox','almacenamiento'):
        ip=a.get('ip',''); aport=a.get('port',0)
        if ip and aport:
            r=subprocess.run(['nc','-z','-w','3',ip,str(aport)],capture_output=True,text=True)
            if r.returncode==0: print(f'🟢 {aid}: {ip}:{aport} alcanzable')
            else: print(f'🔴 {aid}: {ip}:{aport} NO alcanzable'); issues+=1
if issues>0: print(f'\n🔴 {issues} problemas'); sys.exit(1)
else: print('\n✅ Inventario íntegro')
"

#!/bin/bash
# escucha_bus.sh — Escucha activa del Bus de Mensajeria Agentica
# Muestra en tiempo real las acciones de los agentes
# Uso: bash escucha_bus.sh

BUS="http://10.164.1.99:8091"
TOKEN="ura_blackwell_2026"
DELAY=3

echo "============================================="
echo "  ESCUCHA ACTIVA DEL BUS DE MENSAJERIA"
echo "  http://10.164.1.99:8091"
echo "  Pulsa Ctrl+C para salir"
echo "============================================="
echo ""

while true; do
    clear 2>/dev/null || true
    echo "$(date) — Escuchando al Bus..."
    echo ""

    # Agentes registrados
    echo "=== AGENTES EN LINEA ==="
    curl -s --max-time 3 "$BUS/agents" 2>/dev/null | python3 -c "
import json,sys,datetime
try:
    d=json.load(sys.stdin)
    now=datetime.datetime.utcnow()
    for a in d:
        last=a.get('last_heartbeat','')
        if last:
            try:
                t=datetime.datetime.fromisoformat(last.replace('Z','').split('+')[0])
                diff=(now-t).total_seconds()
            except:
                diff=9999
            status='🟢' if diff<120 else '🟡' if diff<600 else '🔴'
        else:
            status='⚪'
        print(f\"  {status} {a['role']:15} {a['id']:25} {a['ip']:15}\")
except: print('  Error leyendo agentes')
"
    echo ""

    # Mensajes recientes en el bus
    echo "=== ULTIMOS EVENTOS ==="
    for agent_id in "opencode-dev" "mac-mini-de-ramon" "gx10-64c3"; do
        msgs=$(curl -s --max-time 2 "$BUS/inbox/$agent_id" 2>/dev/null | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
    for m in d[-3:]:
        print(f\"  [{m.get('sender','?')}] {m.get('topic','?')}: {str(m.get('payload',''))[:80]}\")
except: pass
" 2>/dev/null)
        if [ -n "$msgs" ]; then
            echo "  --- $agent_id ---"
            echo "$msgs"
        fi
    done

    echo ""
    echo "--- Pulse Ctrl+C para salir ---"
    sleep $DELAY
done

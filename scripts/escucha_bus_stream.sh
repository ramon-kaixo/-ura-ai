#!/bin/bash
# escucha_bus_stream.sh — Streaming en vivo del Bus de Mensajeria
# Muestra eventos en tiempo real estilo terminal

BUS="http://10.164.1.99:8091"
TOKEN="ura_blackwell_2026"

echo "🚀 Escucha activa del Bus de Mensajeria Agentica"
echo "   http://10.164.1.99:8091 | Ctrl+C para salir"
echo "============================================="
echo ""

while true; do
    # Cabecera con timestamp
    echo -ne "\033[2J\033[0;0H" 2>/dev/null || clear
    
    # Hora
    echo "$(date '+%H:%M:%S') — 📡 BUS ACTIVO"
    echo ""
    
    # Agentes con estado
    echo "╔═══ AGENTES ═══════════════════════════════════════╗"
    curl -s --max-time 3 "$BUS/agents" 2>/dev/null | python3 -c "
import json,sys,datetime
try:
    d=json.load(sys.stdin)
    now=datetime.datetime.utcnow()
    for a in sorted(d, key=lambda x: x.get('role','')):
        last=a.get('last_heartbeat','')
        if last:
            try:
                t=datetime.datetime.fromisoformat(last.replace('Z','').split('+')[0])
                diff=(now-t).total_seconds()
            except:
                diff=9999
            s='🟢' if diff<120 else '🟡' if diff<600 else '🔴'
            print(f'║ {s} {a[\"role\"]:12} {a[\"id\"]:25} {a.get(\"ip\",\"\"):15}║')
        else:
            print(f'║ ⚪ {a[\"role\"]:12} {a[\"id\"]:25} {a.get(\"ip\",\"\"):15}║')
except: print('║  (error)')
" 2>/dev/null
    echo "╚══════════════════════════════════════════════════════╝"
    echo ""
    
    # Eventos recientes
    echo "╔═══ EVENTOS ════════════════════════════════════════╗"
    for agent in "opencode-dev" "mac-mini-de-ramon" "gx10-64c3"; do
        curl -s --max-time 2 "$BUS/inbox/$agent" 2>/dev/null | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
    for m in d[-3:]:
        s=m.get('sender','?')
        t=m.get('topic','?')
        p=m.get('payload','')[:60]
        print(f'║ [{s}] {t}: {p}')
except: pass
" 2>/dev/null
    done
    echo "╚══════════════════════════════════════════════════════╝"
    
    sleep 5
done

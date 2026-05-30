#!/bin/bash
# agente_policia.sh — Supervisa al Instalador, verifica dispositivos, reporta anomalias
# Se ejecuta cada 5 minutos via crontab

set -euo pipefail

LOG="/var/log/ura_policia.log"
NOTIFICAR="/opt/ura/scripts/notificar.sh"
REGISTRY_URL="http://127.0.0.1:5100/agents"

echo "=== Agente Policia — $(date) ===" | tee -a "$LOG"

# 1. Verificar que el Instalador no ha ejecutado 'rm'
if [ -f /tmp/instalador.log ] && grep -q " rm " /tmp/instalador.log 2>/dev/null; then
    echo "  ALERTA: El Instalador intento usar 'rm'. Bloqueado." | tee -a "$LOG"
    if [ -x "$NOTIFICAR" ]; then
        "$NOTIFICAR" "El Agente Instalador intento borrar archivos" 2>/dev/null || true
    fi
fi

# 2. Verificar dispositivos activos en Tailscale
echo "  Verificando dispositivos..." | tee -a "$LOG"
tailscale status --json 2>/dev/null | python3 -c "
import json, sys
d = json.load(sys.stdin)
for k,v in d.get('Peer',{}).items():
    name = v.get('HostName','?')
    online = v.get('Online', False)
    ips = v.get('TailscaleIPs', [])
    ip = ips[0] if ips else '?'
    status = 'OK' if online else 'OFF'
    print(f'  {status} {name:30} {ip:15}')
    if not online and v.get('LastSeen'):
        print(f'       Last seen: {v[\"LastSeen\"]}')
" 2>/dev/null || true

# 3. Verificar Copilotos (via Registry API)
echo "  Verificando Copilotos registrados..." | tee -a "$LOG"
if curl -s --max-time 5 "$REGISTRY_URL" > /dev/null 2>&1; then
    curl -s "$REGISTRY_URL" 2>/dev/null | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    if isinstance(data, list):
        for a in data:
            print(f'  {a.get(\"type\",\"?\")} {a.get(\"id\",\"?\")} IP:{a.get(\"ip\",\"?\")}')
except: pass
" 2>/dev/null || echo "  Registry sin datos"
else
    echo "  Registry no disponible en $REGISTRY_URL" | tee -a "$LOG"
fi

# 4. Test ping a dispositivos activos
echo "  Ping a dispositivos activos..." | tee -a "$LOG"
tailscale status --json 2>/dev/null | python3 -c "
import json, subprocess, sys
d = json.load(sys.stdin)
for k,v in d.get('Peer',{}).items():
    name = v.get('HostName','?')
    ips = v.get('TailscaleIPs', [])
    if not ips: continue
    try:
        r = subprocess.run(['ping','-c1','-W2',ips[0]], capture_output=True, timeout=5)
        status = 'OK' if r.returncode == 0 else 'SIN RESPUESTA'
        print(f'  {status} {name}')
    except: pass
" 2>/dev/null || true

echo "=== Supervision completada ===" | tee -a "$LOG"

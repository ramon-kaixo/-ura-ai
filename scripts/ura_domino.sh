#!/bin/bash
# ura_domino.sh — Efecto domino: activa OpenClaw en M4, este activa a todos los demas
# 1. Busca dispositivos dormidos y los despierta (Wake-on-LAN)
# 2. Envia senal de ACTIVACION a traves del Bus de Mensajes
# 3. Cada agente al recibirla se registra y se pone en modo observador
# 4. Cuando se le asigna una tarea, ejecuta

set -euo pipefail

REPO="${HOME}/URA/ura_ia_1972"
BUS_URL="http://10.164.1.99:8091"
MALETA="${REPO}/config/maleta.json"
LOG="${REPO}/logs/domino.log"
NOTIFICAR="/opt/ura/scripts/notificar.sh"

mkdir -p "$(dirname "$LOG")"
echo "=== Efecto Domino URA — $(date) ===" | tee "$LOG"

# 1. Cargar maleta (config central con MACs, IPs, roles)
echo "1. Cargando maleta de agentes..." | tee -a "$LOG"
if [ -f "$MALETA" ]; then
    python3 -c "import json; c=json.load(open('$MALETA')); print(f'  {len(c.get(\"agentes\",c.get(\"dispositivos\",[])))} agentes en maleta')" 2>/dev/null
else
    echo "  Maleta no encontrada, creando desde Tailscale..." | tee -a "$LOG"
    tailscale status --json 2>/dev/null | python3 -c "
import json, sys
d = json.load(sys.stdin)
agents = []
for k,v in d.get('Peer',{}).items():
    agents.append({
        'id': v.get('HostName','?'),
        'hostname': v.get('HostName','?'),
        'ip': (v.get('TailscaleIPs') or ['?'])[0],
        'os': v.get('OS','?'),
        'online': v.get('Online', False),
        'role': 'observador',
        'mac': '',
    })
# Add self
agents.append({'id':'mac-mini-de-ramon','hostname':'mac-mini-de-ramon','ip':'100.123.81.101','os':'macos','online':True,'role':'supervisor','mac':''})
with open('$MALETA', 'w') as f:
    json.dump({'version':'1.0','red':'tailscale','agentes':agents}, f, indent=2)
print(f'  Maleta creada con {len(agents)} agentes')
" 2>/dev/null
fi

# 2. Enviar ACTIVATE a traves del Bus
echo "2. Enviando senal de ACTIVACION a la flota..." | tee -a "$LOG"
curl -s -X POST "$BUS_URL/send" \
    -H "Content-Type: application/json" \
    -d "{\"sender\":\"mac-mini-de-ramon\",\"recipient\":\"broadcast\",\"topic\":\"domino/activate\",\"payload\":\"{\\\"from\\\":\\\"mac-mini-de-ramon\\\",\\\"mode\\\":\\\"observador\\\"}\",\"priority\":\"alta\"}" \
    > /dev/null 2>&1 && echo "  Senal enviada" | tee -a "$LOG"

# 3. Wake-on-LAN para dispositivos dormidos
echo "3. Despertando dispositivos dormidos..." | tee -a "$LOG"
python3 -c "
import json, socket, struct, time
try:
    with open('$MALETA') as f:
        cfg = json.load(f)
    for a in cfg.get('agentes', []):
        mac = a.get('mac', '')
        if mac and not a.get('online', False):
            # Enviar magic packet
            mac_clean = mac.replace(':','').replace('-','')
            if len(mac_clean) != 12: continue
            data = bytes.fromhex('FF' * 6 + mac_clean * 16)
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.sendto(data, ('255.255.255.255', 9))
            sock.close()
            print(f'  Magic packet enviado a {a[\"id\"]} ({mac})')
            time.sleep(0.5)
except: pass
" 2>/dev/null

# 4. Esperar a que los agentes se registren
echo "4. Esperando registro de agentes (10s)..." | tee -a "$LOG"
sleep 10

# 5. Verificar cuantos responden
echo "5. Agentes activos tras domino:" | tee -a "$LOG"
curl -s "$BUS_URL/agents" 2>/dev/null | python3 -c "
import json,sys
try:
    agents = json.load(sys.stdin)
    print(f'  {len(agents)} agentes registrados en el Bus')
    for a in sorted(agents, key=lambda x: x.get('role','')):
        icon = {'supervisor':'🟢','nodo_principal':'🟢','copiloto':'🔵','observador':'🟡','windows':'🔵','macos':'🔵','servidor':'🟢'}.get(a.get('role',''),'⚪')
        print(f'  {icon} {a[\"role\"]:12} {a[\"id\"]:30} {a[\"ip\"]:15}')
except: print('  Bus no disponible')
" 2>/dev/null || echo "  Bus no responde"

# 6. Notificar
if [ -x "$NOTIFICAR" ]; then
    TOTAL=$(curl -s "$BUS_URL/agents" 2>/dev/null | python3 -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
    "$NOTIFICAR" "Domino URA: $TOTAL agentes activos" 2>/dev/null || true
fi

echo "" | tee -a "$LOG"
echo "Efecto domino completado. Agentes en modo OBSERVADOR." | tee -a "$LOG"
echo "Para ejecutar tareas: bash scripts/ura_ejecutar.sh <tarea>" | tee -a "$LOG"

#!/bin/bash
# deploy_flota.sh — Despliega y conecta toda la flota URA al Bus de Mensajes
# Ejecutar desde el Mac Mini (Supervisor)
# Uso: bash scripts/deploy_flota.sh

set -euo pipefail

REPO="${HOME}/URA/ura_ia_1972"
BUS_URL="http://10.164.1.99:8091"
LOG="${REPO}/logs/deploy_flota.log"

mkdir -p "$(dirname "$LOG")"
echo "=== Despliegue de Flota URA — $(date) ===" | tee "$LOG"

# 1. Verificar Bus
echo "1. Verificando Bus de Mensajes..." | tee -a "$LOG"
if curl -s --max-time 3 "$BUS_URL/" > /dev/null 2>&1; then
    echo "   Bus OK en $BUS_URL" | tee -a "$LOG"
else
    echo "   Bus NO disponible. Iniciando..." | tee -a "$LOG"
    ssh ramon@10.164.1.99 "sudo systemctl start ura-agent-bus" 2>/dev/null || true
    sleep 2
fi

# 2. Registrar este Mac como Supervisor
echo "2. Registrando Supervisor..." | tee -a "$LOG"
curl -s -X POST "$BUS_URL/heartbeat" \
    -H "Content-Type: application/json" \
    -d '{"id":"mac-mini-de-ramon","hostname":"mac-mini-de-ramon","role":"supervisor","ip":"100.123.81.101"}' > /dev/null

# 3. Desplegar en cada dispositivo accesible via SSH
echo "3. Desplegando Copilotos..." | tee -a "$LOG"
for entry in "ramon@10.164.1.99:gx10-64c3" "barkaixo@100.109.83.16:mac-mini-bar-san-gregorio" "barkaixo@100.90.99.76:mac-mini-san-gregorio"; do
    IFS=':' read -r ssh_user hostname <<< "$entry"

    if ssh -o ConnectTimeout=3 -o BatchMode=yes "$ssh_user" "exit" 2>/dev/null; then
        echo "   Desplegando en $hostname..." | tee -a "$LOG"

        # Instalar copiloto
        ssh "$ssh_user" bash << ENDCLIENT
            mkdir -p /opt/ura/{agents,logs,cuarentena}
            curl -sL https://raw.githubusercontent.com/ramonesnaola/URA/refs/heads/main/scripts/agent_heartbeat.sh -o /opt/ura/scripts/heartbeat.sh 2>/dev/null || cat > /opt/ura/scripts/heartbeat.sh << 'EOF'
$(cat "$REPO/scripts/agent_heartbeat.sh")
EOF
            chmod +x /opt/ura/scripts/heartbeat.sh
            BUS_URL=$BUS_URL AGENT_ROLE=copiloto nohup bash /opt/ura/scripts/heartbeat.sh > /opt/ura/logs/heartbeat.log 2>&1 &
            echo "   Heartbeat iniciado en $hostname"
ENDCLIENT

        # Registrar
        curl -s -X POST "$BUS_URL/heartbeat" \
            -H "Content-Type: application/json" \
            -d "{\"id\":\"$hostname\",\"hostname\":\"$hostname\",\"role\":\"copiloto\",\"ip\":\"$(echo $ssh_user | cut -d@ -f2)\"}" > /dev/null
        echo "   Registrado: $hostname" | tee -a "$LOG"
    else
        echo "   No accesible: $hostname" | tee -a "$LOG"
    fi
done

# 4. Resumen final
echo "" | tee -a "$LOG"
echo "=== FLOTA ACTIVA ===" | tee -a "$LOG"
curl -s "$BUS_URL/agents" 2>/dev/null | python3 -c "
import json,sys
agents=json.load(sys.stdin)
print(f'  {len(agents)} agentes en el Bus')
for a in sorted(agents, key=lambda x: x['role']):
    print(f'  {a[\"role\"]:12} {a[\"id\"]:30} {a[\"ip\"]:15}')
" | tee -a "$LOG"
echo "" | tee -a "$LOG"
echo "Despliegue completado." | tee -a "$LOG"

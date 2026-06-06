#!/bin/bash
set -euo pipefail
# conectar_servidor_externo.sh — Despliega proxy de contraste en servidor cloud
# ==============================================================================
# INSTRUCCIONES:
#   1. Pega la IP pública de tu servidor en SERVER_IP abajo
#   2. Pon tu usuario SSH (root, ubuntu, debian, etc.)
#   3. Ejecuta: bash conectar_servidor_externo.sh
# ==============================================================================

# ── CAMBIA ESTOS VALORES ──────────────────────────────────────────────────────
SERVER_IP="__PEGA_AQUI_LA_IP_DEL_SERVIDOR__"
SERVER_USER="root"  # Cambia si es necesario (ubuntu, debian, admin, etc.)
SSH_KEY="~/.ssh/id_ed25519"
# ──────────────────────────────────────────────────────────────────────────────

echo "=== Despliegue en servidor externo: $SERVER_IP ==="

# 1. Instalar Tailscale y unir a la red
ssh -o StrictHostKeyChecking=no -i "$SSH_KEY" "${SERVER_USER}@${SERVER_IP}" bash << 'REMOTE'
set -e
echo "Instalando Tailscale..."
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up --authkey="${TS_AUTH_KEY:-}" 2>/dev/null || {
  echo "Necesitas autenticar Tailscale manualmente."
  echo "Ejecuta en otra terminal: ssh ${SERVER_USER}@${SERVER_IP} 'sudo tailscale up'"
  echo "Luego vuelve a ejecutar este script."
  exit 1
}
echo "Esperando IP de Tailscale..."
sleep 3
TS_IP=$(tailscale ip -4)
echo "Tailscale activo en: $TS_IP"
REMOTE

# 2. Transferir proxy_contraste.py
echo "Transfiriendo proxy_contraste.py..."
scp -i "$SSH_KEY" /opt/ura/agents/proxy_contraste.py "${SERVER_USER}@${SERVER_IP}:/opt/ura/agents/proxy_contraste.py"

# 3. Instalar dependencias y crear servicio
ssh -i "$SSH_KEY" "${SERVER_USER}@${SERVER_IP}" bash << 'REMOTE2'
set -e
sudo apt-get update -qq
sudo apt-get install -y -qq python3-pip
pip3 install --break-system-packages fastapi uvicorn openai anthropic
TS_IP=$(tailscale ip -4)
sudo tee /etc/systemd/system/ura-contraste.service > /dev/null << SERVEOF
[Unit]
Description=URA Contrast Proxy (Cloud)
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/ura/agents
Environment="OPENAI_FREE_KEY=${OPENAI_FREE_KEY}"
Environment="ANTHROPIC_FREE_KEY=${ANTHROPIC_FREE_KEY}"
ExecStart=$(which python3) -m uvicorn proxy_contraste:app --host ${TS_IP} --port 8002 --workers 1
Restart=always

[Install]
WantedBy=multi-user.target
SERVEOF
sudo systemctl daemon-reload
sudo systemctl enable --now ura-contraste.service
sleep 2
curl -s http://${TS_IP}:8002/health
REMOTE2

echo "=== Servidor externo desplegado ==="

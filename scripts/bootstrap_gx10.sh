#!/bin/bash
set -euo pipefail
# bootstrap_gx10.sh - Configuracion automatica del GX10 tras instalar Ubuntu
# Ejecutar en el GX10 despues de la instalacion de Ubuntu Server

echo "========================================="
echo "  URA Bootstrap GX10"
echo "  $(date)"
echo "========================================="

# 1. Sistema base
echo "[1/6] Actualizando sistema..."
sudo apt update && sudo apt upgrade -y
sudo apt install -y docker.io curl jq nginx openssh-server python3 python3-pip python3-venv git rsync net-tools

# 2. Tailscale
echo "[2/6] Instalando Tailscale..."
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up --accept-routes --ssh

# 3. Ollama
echo "[3/6] Instalando Ollama..."
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5-coder:14b &
ollama pull llama3.2-vision:11b &
wait

# 4. SSH
echo "[4/6] Configurando SSH..."
mkdir -p ~/.ssh
chmod 700 ~/.ssh
ssh-keygen -t ed25519 -f ~/.ssh/id_ura -N "" -C "ura@gx10-ura"
sudo systemctl enable ssh
sudo systemctl start ssh

# 5. URA
echo "[5/6] Sincronizando URA..."
MAC_IP=$(ip route get 10.164.1.1 2>/dev/null | awk '{print $7}' || echo "10.164.1.17")
mkdir -p ~/URA
rsync -avz "ramonesnaola@${MAC_IP}:/Users/ramonesnaola/URA/ura_ia_1972/" ~/URA/ura_ia_1972/ 2>/dev/null || {
    echo "⚠️ No se pudo sincronizar URA. Intentando con Tailscale..."
    rsync -avz "ramonesnaola@100.123.81.101:/Users/ramonesnaola/URA/ura_ia_1972/" ~/URA/ura_ia_1972/ 2>/dev/null || true
}

cd ~/URA/ura_ia_1972
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt 2>/dev/null || true

# 6. Servicios
echo "[6/6] Iniciando servicios..."
nohup .venv/bin/python3 agents/registry_api.py &>/tmp/ura_registry.log &
nohup .venv/bin/python3 web/ura_dashboard.py &>/tmp/ura_dashboard.log &

# Auto-start on boot
cat > ~/.config/systemd/user/ura-registry.service << EOF
[Unit]
Description=URA Registry API
After=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/ura/URA/ura_ia_1972
ExecStart=/home/ura/URA/ura_ia_1972/.venv/bin/python3 agents/registry_api.py
Restart=always

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable ura-registry.service

echo ""
echo "========================================="
echo "  ✅ GX10 configurado"
echo "========================================="
echo ""
echo "Hostname: $(hostname)"
echo "Tailscale: $(tailscale ip -4)"
echo "Ollama: $(ollama list | wc -l) modelos"
echo "URA: $(ps aux | grep -c '[r]egistry_api') procesos"

#!/bin/bash
# bootstrap.sh - Activa SSH y copia la clave publica del Mac al nodo remoto
set -euo pipefail

MAC_IP="${MAC_IP:-10.164.1.17}"
AUTH_KEY="${1:-}"

echo "[bootstrap] Iniciando configuracion del nodo..."

# Punto 2: Activar SSH
if command -v systemctl >/dev/null 2>&1; then
    systemctl enable ssh --now 2>/dev/null || systemctl enable sshd --now 2>/dev/null || true
elif command -v service >/dev/null 2>&1; then
    service ssh start 2>/dev/null || service sshd start 2>/dev/null || true
fi

# Configurar usuario ura (Punto 11)
if ! id -u ura >/dev/null 2>&1; then
    useradd -m -s /bin/bash ura 2>/dev/null || adduser --disabled-password --gecos "" ura 2>/dev/null || true
fi

# Copiar clave publica del Mac
mkdir -p /root/.ssh /home/ura/.ssh
curl -sf "http://${MAC_IP}:8080/ura_pubkey.pub" >> /root/.ssh/authorized_keys 2>/dev/null || true
curl -sf "http://${MAC_IP}:8080/ura_pubkey.pub" >> /home/ura/.ssh/authorized_keys 2>/dev/null || true
chmod 600 /root/.ssh/authorized_keys /home/ura/.ssh/authorized_keys 2>/dev/null || true
chmod 700 /root/.ssh /home/ura/.ssh 2>/dev/null || true
chown -R ura:ura /home/ura/.ssh 2>/dev/null || true

# Instalar Tailscale si no esta presente
if ! command -v tailscale >/dev/null 2>&1; then
    curl -fsSL https://tailscale.com/install.sh | sh 2>/dev/null || true
fi

# Unirse a Tailscale con auth key efimera
if [ -n "$AUTH_KEY" ]; then
    tailscale up --authkey="$AUTH_KEY" --accept-routes 2>/dev/null || true
fi

# Crear estructura URA
mkdir -p /opt/ura/data/registry/eventos /opt/ura/data/registry/procesados /opt/ura/data/planes
mkdir -p /opt/ura/sandbox/Aprendizaje/Enjambre/informes
echo "1" > /opt/ura/version.txt

echo "[bootstrap] Nodo configurado correctamente"

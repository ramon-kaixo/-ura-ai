#!/bin/bash
set -euo pipefail
# setup_ssh_ura.sh - Configura clave SSH dedicada para URA
URA_SSH_DIR="/Users/ramonesnaola/.ssh"
URA_SSH_KEY="${URA_SSH_DIR}/id_ura_gx10"

echo "Configurando clave SSH para URA..."

# 1. Crear directorio y clave sin passphrase (si no existe)
mkdir -p "$URA_SSH_DIR"
chmod 700 "$URA_SSH_DIR"

if [ ! -f "$URA_SSH_KEY" ]; then
    echo "Generando nueva clave ed25519..."
    ssh-keygen -t ed25519 -f "$URA_SSH_KEY" -N "" -C "ura@mac-mini"
else
    echo "Clave existente encontrada: $URA_SSH_KEY"
fi

# 2. Configurar alias SSH (solo si no existe la seccion gx10)
if ! grep -q "Host gx10" "${URA_SSH_DIR}/config" 2>/dev/null; then
    cat >> "${URA_SSH_DIR}/config" << EOF

# URA - GX10
Host gx10
    HostName 10.164.1.99
    User ramon
    IdentityFile ${URA_SSH_KEY}
    StrictHostKeyChecking accept-new
    UserKnownHostsFile ${URA_SSH_DIR}/known_hosts

Host gx10-ts
    HostName 10.164.1.99
    User ramon
    ProxyCommand tailscale dial tcp 10.164.1.99:22
    StrictHostKeyChecking accept-new
    UserKnownHostsFile ${URA_SSH_DIR}/known_hosts
    IdentityFile ${URA_SSH_KEY}
EOF
    chmod 600 "${URA_SSH_DIR}/config"
    echo "Configuracion SSH añadida"
else
    echo "Configuracion SSH ya existente"
fi

# 3. Iniciar agente SSH y añadir la clave
SSH_AGENT_SOCK="${URA_SSH_DIR}/agent.sock"
if [ -S "$SSH_AGENT_SOCK" ]; then
    rm -f "$SSH_AGENT_SOCK"
fi
eval "$(ssh-agent -s)" > /dev/null 2>&1
ln -sf "${SSH_AUTH_SOCK:-/dev/null}" "$SSH_AGENT_SOCK" 2>/dev/null || true
ssh-add "$URA_SSH_KEY" 2>/dev/null || true

echo "Clave SSH de URA configurada: $URA_SSH_KEY"
echo "Agent sock: $SSH_AGENT_SOCK"

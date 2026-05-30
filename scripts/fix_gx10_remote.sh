#!/bin/bash
# fix_gx10_remote.sh - URA ejecuta esto desde el Mac via SSH key
set -euo pipefail

GX10_ALIAS="${GX10_SSH_ALIAS:-gx10}"

echo "   Reparando GX10 remotamente via SSH alias: $GX10_ALIAS..."

ssh "$GX10_ALIAS" << 'SSHEOF'
    set -e
    echo "   === Reparando DNS ==="
    echo "nameserver 8.8.8.8" | sudo tee /etc/resolv.conf
    echo "nameserver 1.1.1.1" | sudo tee -a /etc/resolv.conf
    sudo systemctl restart systemd-resolved 2>/dev/null || true

    echo "   === Reparando Tailscale ==="
    if ! tailscale status >/dev/null 2>&1; then
        tailscale up --accept-routes 2>/dev/null || true
    fi

    echo "   === Verificando Ollama ==="
    if ! systemctl is-active ollama >/dev/null 2>&1; then
        sudo systemctl start ollama 2>/dev/null || true
    fi

    echo "   === Asegurando scripts URA ==="
    mkdir -p /opt/ura/scripts
    find /opt/ura/scripts -name "*.sh" -exec chmod +x {} \;

    echo "   === Verificando conectividad ==="
    if ping -c 1 google.com >/dev/null 2>&1; then
        echo "   OK: Internet restaurada"
    else
        echo "   WARN: Sin conectividad a Internet"
    fi
SSHEOF

if [ $? -eq 0 ]; then
    echo "   Reparacion remota completada"
    curl -s -X POST http://localhost:5105/sistema/gx10_reparado 2>/dev/null || true
else
    echo "   Fallo en reparacion remota"
    REPO="$(cd "$(dirname "$0")/.." && pwd)"
    NOTIF="${REPO}/scripts/notificar.sh"
    if [ -x "$NOTIF" ]; then
        "$NOTIF" "ALERTA: No se pudo reparar GX10 automaticamente"
    fi
fi

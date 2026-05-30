#!/bin/bash
# deploy_gx10.sh - Despliegue completo y verificacion del GX10 desde el Mac
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
GX10_ALIAS="gx10"
GX10_IP="10.164.1.99"
HEALTH_PORT=5103

echo "========================================="
echo "  URA - Despliegue y Verificacion GX10"
echo "  $(date)"
echo "========================================="

# 1. Verificar conexion SSH
echo ""
echo "[1/6] Verificando conexion SSH..."
if ssh -o ConnectTimeout=5 "$GX10_ALIAS" "echo conectado" >/dev/null 2>&1; then
    echo "   ✅ SSH al GX10 funciona"
else
    echo "   ❌ SSH al GX10 fallo. Ejecuta: bash scripts/setup_ssh_gx10.sh"
    exit 1
fi

# 2. Estado de servicios
echo ""
echo "[2/6] Estado de servicios en GX10..."
ssh "$GX10_ALIAS" << 'EOF'
    echo "   Ollama:      $(systemctl is-active ollama 2>/dev/null || echo 'inactive')"
    echo "   Tailscale:   $(systemctl is-active tailscaled 2>/dev/null || echo 'inactive')"
    echo "   Resolved:    $(systemctl is-active systemd-resolved 2>/dev/null || echo 'inactive')"
    echo "   n8n:         $(systemctl is-active n8n 2>/dev/null || echo 'inactive')"
EOF

# 3. Health API
echo ""
echo "[3/6] Verificando Health API (puerto $HEALTH_PORT)..."
if curl -s --max-time 5 "http://${GX10_IP}:${HEALTH_PORT}/health" >/dev/null 2>&1; then
    echo "   ✅ Health API responde"
    curl -s --max-time 5 "http://${GX10_IP}:${HEALTH_PORT}/health" | python3 -m json.tool 2>/dev/null || true
else
    echo "   ⚠️ Health API no responde (puede ser normal si no esta iniciado)"
fi

# 4. Copiar scripts al GX10
echo ""
echo "[4/6] Copiando scripts al GX10..."
ssh "$GX10_ALIAS" "mkdir -p /opt/ura/scripts"

for script in fix_gx10_remote.sh fix_gx10.sh backup_discos_locales.sh network_autorepair.sh; do
    if [ -f "$REPO/scripts/$script" ]; then
        scp "$REPO/scripts/$script" "$GX10_ALIAS:/opt/ura/scripts/" 2>/dev/null && echo "   ✅ $script" || echo "   ⚠️ $script (fallo scp)"
    else
        echo "   ⏭️ $script (no existe en repo)"
    fi
done

ssh "$GX10_ALIAS" "chmod +x /opt/ura/scripts/*.sh 2>/dev/null || true"
echo "   Permisos actualizados"

# 5. Ejecutar reparacion completa
echo ""
echo "[5/6] Ejecutando reparacion completa..."
ssh "$GX10_ALIAS" << 'EOF'
    echo "   === Reparando DNS ==="
    echo "nameserver 8.8.8.8" | sudo tee /etc/resolv.conf
    echo "nameserver 1.1.1.1" | sudo tee -a /etc/resolv.conf
    sudo systemctl restart systemd-resolved 2>/dev/null || true

    echo "   === Verificando Tailscale ==="
    if ! tailscale status >/dev/null 2>&1; then
        tailscale up --accept-routes 2>/dev/null || true
    fi

    echo "   === Verificando Ollama ==="
    if ! systemctl is-active ollama >/dev/null 2>&1; then
        sudo systemctl start ollama 2>/dev/null || true
    fi

    echo "   === Verificando conectividad ==="
    if ping -c 1 google.com >/dev/null 2>&1; then
        echo "   ✅ Internet OK"
    else
        echo "   ⚠️ Sin Internet"
    fi
EOF
echo "   ✅ Reparacion completada"

# 6. Configurar cron de backups
echo ""
echo "[6/6] Configurando cron de backups..."
ssh "$GX10_ALIAS" << 'EOF'
    sudo mkdir -p /etc/cron.d
    echo '0 2 * * * root /opt/ura/scripts/backup_discos_locales.sh' | sudo tee /etc/cron.d/ura_backup >/dev/null
    sudo chmod 644 /etc/cron.d/ura_backup
    echo "   ✅ Cron configurado (backup diario a las 02:00)"
EOF

# Resumen final
echo ""
echo "========================================="
echo "  Despliegue completado"
echo "========================================="
echo ""
echo "Proximos pasos:"
echo "  1. Iniciar mock TPV: python3 $REPO/scripts/mock_tpv_api.py"
echo "  2. Ver logs autonomia: tail -f /tmp/autonomia.log"
echo "  3. Prueba estres: ssh gx10 'sudo iptables -A OUTPUT -j DROP'"
echo "  4. Restaurar: ssh gx10 'sudo iptables -F'"
echo ""

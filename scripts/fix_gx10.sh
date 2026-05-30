#!/bin/bash
# fix_gx10.sh - Ejecutar localmente en el GX10 (como root)
# Repara DNS, Tailscale y cron de backups en un solo paso
set -euo pipefail

echo "=== Fijando DNS ==="
cat > /etc/resolv.conf << EOF
nameserver 8.8.8.8
nameserver 1.1.1.1
EOF

echo "=== Reiniciando systemd-resolved ==="
systemctl restart systemd-resolved 2>/dev/null || true

echo "=== Reconfigurando Tailscale ==="
tailscale up --accept-routes 2>/dev/null || true

echo "=== Asegurando cron de backups ==="
mkdir -p /opt/ura/scripts
cat > /etc/cron.d/ura_backup << 'CRONEOF'
0 2 * * * root /opt/ura/scripts/backup_discos_locales.sh
CRONEOF
chmod 644 /etc/cron.d/ura_backup

echo "=== Verificando conectividad ==="
if ping -c 2 google.com >/dev/null 2>&1; then
    echo "OK: Internet restaurada"
else
    echo "WARN: Sin conectividad a Internet"
fi

echo "=== Hecho. Ahora URA puede gestionar el GX10 remotamente ==="

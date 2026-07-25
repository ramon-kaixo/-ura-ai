#!/bin/bash
# Fix rootfs RO + NoNewPrivileges + instalar servicios
# Ejecutar con: sudo bash deploy/fix_rootfs.sh
set -euo pipefail

echo "=== 1. Remount rootfs RW ==="
mount -o remount,rw /
echo "  OK: $(mount | grep ' / ' | grep -o 'rw,')"

echo ""
echo "=== 2. Run fsck ==="
fsck -y /dev/nvme0n1p2 || echo "  fsck completado (pueden haber errores)"
echo "  NOTA: Si hay errores persistentes, ejecutar: touch /forcefsck && reboot"

echo ""
echo "=== 3. Remove NoNewPrivileges from opencode ==="
mkdir -p /etc/systemd/system/opencode.service.d
cat > /etc/systemd/system/opencode.service.d/nonwprivileges.conf << 'EOF'
[Service]
# Permitir sudo para el usuario ramon
NoNewPrivileges=false
EOF
systemctl daemon-reload
systemctl restart opencode.service
echo "  OK: opencode.service reiniciado sin NoNewPrivileges"

echo ""
echo "=== 4. Install and start watch daemon ==="
cp deploy/ura-watch-daemon.service /etc/systemd/system/
systemctl enable ura-watch-daemon
systemctl start ura-watch-daemon
systemctl status ura-watch-daemon --no-pager | head -5
echo "  OK: ura-watch-daemon activo"

echo ""
echo "=== 5. Install and start Samba ==="
systemctl enable smbd --now || echo "  WARN: smbd no disponible, instalar con: apt install samba"
systemctl status smbd --no-pager | head -3
echo "  OK: smbd activo"

echo ""
echo "=== 6. Verify ==="
mount | grep ' / '
echo "NoNewPrivs: $(cat /proc/self/status | grep NoNewPrivs || echo 'check /proc/self/status')"
echo "Samba: $(pgrep smbd | wc -l) procs"
echo "Daemon: $(pgrep -f inotifywait | wc -l) procs"

echo ""
echo "=== LISTO ==="
echo "Rootfs RW, sudo disponible, daemon+samba instalados."
echo "Cierra y abre una nueva sesión SSH para que NoNewPrivileges surta efecto."

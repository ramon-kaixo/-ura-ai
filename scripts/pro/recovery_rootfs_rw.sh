#!/bin/bash
# recovery_rootfs_rw.sh — Recuperación de rootfs RO tras reboot
# EJECUTAR DESDE CONSOLA FÍSICA (GRUB + terminal)
# 
# PASO 1: En GRUB, pulsar 'e' sobre "Ubuntu"
# PASO 2: Buscar "ro quiet splash" y CAMBIAR a "rw quiet splash"
# PASO 3: Pulsar Ctrl+X o F10 para arrancar
# PASO 4: En la terminal, ejecutar este script:
#         bash ~/URA/ura_ia_1972/scripts/pro/recovery_rootfs_rw.sh

set -euo pipefail

echo "=== 1. Remontando rootfs como RW ==="
mount -o remount,rw /
echo "OK — rootfs RW"

echo "=== 2. Remontando /run como RW ==="
mount -o remount,rw /run
echo "OK — /run RW"

echo "=== 3. Aplicando sudoers restrictivo ==="
tee /etc/sudoers.d/ura-rescate > /dev/null <<'SUDOERS'
# URA — comandos específicos sin password (restringido desde ALL)
ramon ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart ura-mochila.service
ramon ALL=(ALL) NOPASSWD: /usr/bin/systemctl daemon-reload
ramon ALL=(ALL) NOPASSWD: /usr/bin/systemctl start ura-*.service
ramon ALL=(ALL) NOPASSWD: /usr/bin/systemctl stop ura-*.service
ramon ALL=(ALL) NOPASSWD: /usr/bin/journalctl -u ura-*.service
ramon ALL=(ALL) NOPASSWD: /sbin/reboot
SUDOERS
visudo -c -f /etc/sudoers.d/ura-rescate && echo "sudoers OK" || echo "ERROR en sudoers"

echo "=== 4. GRUB: añadir rw al kernel cmdline ==="
cp /etc/default/grub /etc/default/grub.bak
sed -i 's/GRUB_CMDLINE_LINUX_DEFAULT="/GRUB_CMDLINE_LINUX_DEFAULT="rw /' /etc/default/grub
echo "GRUB_CMDLINE_LINUX_DEFAULT actualizado:"
grep "^GRUB_CMDLINE_LINUX_DEFAULT" /etc/default/grub

update-grub
echo "GRUB actualizado — próximo reboot arrancará RW automáticamente"

echo "=== 5. Recargando configs systemd ==="
systemctl daemon-reload

echo "=== 6. Restaurando servicios ==="
systemctl restart model-router.service
systemctl reset-failed ura-contraste.service
systemctl start ura-contraste.service

echo "=== 7. Verificando ==="
findmnt -n -o OPTIONS /
findmnt -n -o OPTIONS /run
systemctl is-active model-router ura-contraste ura-mochila ura-heartbeat

echo ""
echo "=== RECOVERY COMPLETADO ==="
echo "Rootfs y /run RW. GRUB configurado para arranque RW permanente."
echo "Próximo reinicio ya no necesitará este script."

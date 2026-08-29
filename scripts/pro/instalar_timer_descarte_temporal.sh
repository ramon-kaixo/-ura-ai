#!/bin/bash
# Instalación del timer diario de limpieza del descarte temporal (requiere rootfs RW).
# Ejecutar con sudo (una sola vez, en GX10/ASUS):
#   sudo bash scripts/pro/instalar_timer_descarte_temporal.sh
#
# Pasos:
#   1. Remontar rootfs RW (si está RO)
#   2. Copiar units systemd
#   3. daemon-reload + enable + start
#   4. Remontar rootfs RO (volver al estado original)
#   5. Verificación (systemctl list-timers | grep descarte)

set -euo pipefail

ROOTFS_MOUNTED_RO=0
if grep -q " / ext4 (ro" /proc/mounts; then
	echo "[1/5] Rootfs está RO — remontando RW..."
	mount -o remount,rw /
	ROOTFS_MOUNTED_RO=1
fi

echo "[2/5] Copiando units systemd..."
cp /home/ramon/URA/ura_ia_1972/deploy/ura-descarte-temporal.service /etc/systemd/system/
cp /home/ramon/URA/ura_ia_1972/deploy/ura-descarte-temporal.timer /etc/systemd/system/

echo "[3/5] Recargando systemd..."
systemctl daemon-reload

echo "[4/5] Habilitando timer (diario)..."
systemctl enable --now ura-descarte-temporal.timer
systemctl start ura-descarte-temporal.timer

if [ "$ROOTFS_MOUNTED_RO" = "1" ]; then
	echo "[5/5] Restaurando rootfs a RO..."
	mount -o remount,ro /
fi

echo ""
echo "=== VERIFICACIÓN ==="
systemctl is-active ura-descarte-temporal.timer
systemctl list-timers ura-descarte-temporal.timer --no-pager
echo "OK: timer instalado (limpieza diaria de /home/ramon/URA/descarte_temporal -> >=90 dias sin uso)"

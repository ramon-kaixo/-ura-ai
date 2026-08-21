#!/bin/bash
# Instalación del timer nightly del pipeline de cobertura (requiere rootfs RW).
# Ejecutar con sudo (una sola vez):
#   sudo bash scripts/pro/instalar_timer_cobertura.sh
#
# Pasos:
#   1. Remontar rootfs RW (si está RO)
#   2. Copiar units systemd
#   3. daemon-reload + enable + start
#   4. Remontar rootfs RO (volver al estado original)
#   5. Verificación

set -euo pipefail

ROOTFS_MOUNTED_RO=0
if grep -q " / ext4 (ro" /proc/mounts; then
    echo "[1/5] Rootfs está RO — remontando RW..."
    mount -o remount,rw /
    ROOTFS_MOUNTED_RO=1
fi

echo "[2/5] Copiando units systemd..."
cp /home/ramon/URA/ura_ia_1972/deploy/ura-cobertura.service /etc/systemd/system/
cp /home/ramon/URA/ura_ia_1972/deploy/ura-cobertura.timer /etc/systemd/system/

echo "[3/5] Recargando systemd..."
systemctl daemon-reload

echo "[4/5] Habilitando timer (diario 02:30)..."
systemctl enable --now ura-cobertura.timer
systemctl start ura-cobertura.timer

if [ "$ROOTFS_MOUNTED_RO" = "1" ]; then
    echo "[5/5] Restaurando rootfs a RO..."
    mount -o remount,ro /
fi

echo ""
echo "=== VERIFICACIÓN ==="
systemctl is-active ura-cobertura.timer
systemctl list-timers ura-cobertura.timer --no-pager
echo "OK: timer instalado (pipeline_cobertura --reporte cada día a las 02:30)"

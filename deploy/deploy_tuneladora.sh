#!/bin/bash
set -euo pipefail

# deploy_tuneladora.sh — Instala el nuevo pipeline y deja ambos en paralelo
# Ejecutar CON sudo desde SSH

echo "=== Instalando tuneladora v2 ==="

# 1. Copiar service + timer
sudo cp deploy/ura-maintenance-v2.service /etc/systemd/system/
sudo cp deploy/ura-maintenance-v2.timer /etc/systemd/system/

# 2. Recargar systemd
sudo systemctl daemon-reload

# 3. Habilitar e iniciar el nuevo timer
sudo systemctl enable ura-maintenance-v2.timer
sudo systemctl start ura-maintenance-v2.timer

echo ""
echo "=== Estado: ambos pipelines activos ==="
echo "  viejo: ura-maintenance.timer  → mantenimiento/ura_maintenance.py"
echo "  nuevo: ura-maintenance-v2.timer → scripts/pro/tuneladora_mantenimiento.py"
echo ""
echo "Para monitorizar:"
echo "  journalctl -u ura-maintenance-v2.service -f"
echo "  systemctl list-timers | grep ura-maintenance"
echo ""
echo "Para cambiar al nuevo definitivamente (tras validar):"
echo "  sudo systemctl disable --now ura-maintenance.timer"
echo "  sudo systemctl enable --now ura-maintenance-v2.timer"

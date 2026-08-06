#!/bin/bash
# stage_hardening.sh — Prueba de hardening en un servicio antes de aplicar a todos
#
# Uso: ./stage_hardening.sh ura-mochila.service
#   Aplica hardening de prueba al servicio, verifica que arranca,
#   si falla, revierte automáticamente.
set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Uso: $0 <servicio.service>"
    echo "Ej:  $0 ura-mochila.service"
    exit 1
fi

SERVICE="$1"
DROP_DIR="/etc/systemd/system/${SERVICE}.d"
BACKUP_DIR="/tmp/ura_hardening_test/${SERVICE}"

echo "=== Stage Hardening para $SERVICE ==="
echo "1. Creando configuración de prueba..."

mkdir -p "$BACKUP_DIR"
# Backup de drop-ins existentes
if [ -d "$DROP_DIR" ]; then
    cp -r "$DROP_DIR" "$BACKUP_DIR/dropins"
fi

# Backup del service file (resuelve ruta real via systemctl cat)
SERVICE_FILE_PATH=$(systemctl cat "$SERVICE" 2>/dev/null | head -1 | sed 's/^# //')
if [ -n "$SERVICE_FILE_PATH" ] && [ -f "$SERVICE_FILE_PATH" ]; then
    cp "$SERVICE_FILE_PATH" "$BACKUP_DIR/$(basename "$SERVICE_FILE_PATH")"
fi

echo "2. Aplicando hardening de prueba..."
sudo mkdir -p "$DROP_DIR"
sudo bash -c "cat > $DROP_DIR/stage-hardening.conf" << EOF
[Service]
# Hardening de prueba — verificar compatibilidad
PrivateTmp=true
ProtectSystem=full
ProtectHome=read-only
NoNewPrivileges=true
MemoryDenyWriteExecute=true
EOF

echo "3. Probando..."
sudo systemctl daemon-reload
if sudo systemctl restart "$SERVICE" 2>/dev/null; then
    sleep 2
    if systemctl is-active -q "$SERVICE" 2>/dev/null; then
        echo "   ✅ $SERVICE activo con hardening"
        echo "   Aplicar al resto: copiar stage-hardening.conf al drop-in de cada servicio"
        exit 0
    fi
fi

echo "   ❌ $SERVICE falló con hardening. Revirtiendo..."
sudo rm -f "$DROP_DIR/stage-hardening.conf"
if [ -d "$BACKUP_DIR/dropins" ]; then
    cp -r "$BACKUP_DIR/dropins"/* "$DROP_DIR/"
fi
sudo systemctl daemon-reload
sudo systemctl restart "$SERVICE" 2>/dev/null || true
echo "   ✅ Hardening revertido. $SERVICE restaurado."
exit 1
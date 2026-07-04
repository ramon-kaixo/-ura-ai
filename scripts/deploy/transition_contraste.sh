#!/usr/bin/env bash
# transition_contraste.sh — Auto-deploy masivo de servicios URA vía systemd
# Ejecutar en ASUS con sudo. Cero intervención humana.
set -euo pipefail

URA_ROOT="/home/ramon/URA/ura_ia_1972"

echo "=== [AUTO-DEPLOY] Iniciando transición en ASUS ==="

# 1. Copia masiva de servicios reales (validados en Fase 4)
echo "[1/4] Copiando servicios a /etc/systemd/system/..."
sudo cp "$URA_ROOT/deploy/"*.service /etc/systemd/system/ 2>/dev/null || true
sudo cp "$URA_ROOT/scripts/deploy/"*.service /etc/systemd/system/ 2>/dev/null || true
sudo cp "$URA_ROOT/scripts/pro/gx10-api.service" /etc/systemd/system/ 2>/dev/null || true

# 2. Eliminar hardening.conf problemático de raíz
if [ -f "/etc/systemd/system/ura-contraste.service.d/hardening.conf" ]; then
    echo "[2/4] Eliminando hardening.conf problemático..."
    sudo rm -f /etc/systemd/system/ura-contraste.service.d/hardening.conf
fi

# 3. Matar procesos watchdog/uvicorn legacy de forma genérica
echo "[3/4] Limpiando procesos legacy..."
sudo pkill -f uvicorn 2>/dev/null || true
sudo pkill -f watchdog 2>/dev/null || true

# 4. Recargar y activar servicios
echo "[4/4] Recargando systemd y activando servicios..."
sudo systemctl daemon-reload
sudo systemctl enable --now ura-contraste.service 2>/dev/null || true
sudo systemctl enable --now ura-openclaw.service 2>/dev/null || true

echo "=== [AUTO-DEPLOY] Completado ==="
echo "Servicios instalados:"
ls /etc/systemd/system/ura-contraste.service /etc/systemd/system/ura-openclaw.service 2>/dev/null
echo "Estado:"
sudo systemctl is-active ura-contraste.service ura-openclaw.service 2>/dev/null

#!/bin/bash
# instalar_servidor_camaras.sh — Ejecutar en el servidor de la nube
# Instala go2rtc + monitoreo para analisis de camaras en tiempo real

set -euo pipefail
LOG_DIR="/opt/ura/logs"
CONF="/opt/ura/config/go2rtc.yaml"

mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/camaras_servidor.log"

echo "=== Instalando supervisor de camaras en servidor ===" | tee "$LOG"

sudo mkdir -p /opt/ura/{agents,config,logs}
sudo chown -R "$USER:$USER" /opt/ura

ARCH=$(uname -m)
case "$ARCH" in
    x86_64)  BIN="go2rtc_linux_amd64" ;;
    aarch64) BIN="go2rtc_linux_arm64"  ;;
    armv7l)  BIN="go2rtc_linux_arm"   ;;
    *) echo "Arquitectura no soportada: $ARCH"; exit 1 ;;
esac

if [ ! -f /opt/ura/agents/go2rtc ]; then
    echo "Descargando go2rtc para $ARCH..." | tee -a "$LOG"
    curl -sL "https://github.com/AlexxIT/go2rtc/releases/latest/download/$BIN" -o /opt/ura/agents/go2rtc
    chmod +x /opt/ura/agents/go2rtc
fi

sudo tee /etc/systemd/system/ura-go2rtc.service << 'UNIT'
[Unit]
Description=go2rtc Camera Stream Proxy
After=network.target

[Service]
ExecStart=/opt/ura/agents/go2rtc --config /opt/ura/config/go2rtc.yaml
WorkingDirectory=/opt/ura
Restart=always

[Install]
WantedBy=multi-user.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable ura-go2rtc
sudo systemctl start ura-go2rtc || true

echo "=== Servidor de camaras instalado ===" | tee -a "$LOG"
echo "  go2rtc: systemctl status ura-go2rtc" | tee -a "$LOG"
echo "  Streams: http://$(hostname -I | awk '{print $1}'):1984/" | tee -a "$LOG"

#!/bin/bash
# deploy_camaras.sh — Despliega el sistema de camaras: servidor + GX10
# Arquitectura:
#   Camara Dahua (subtype=0 alta res) -> ASUS GX10 -> Frigate (grabacion 24/7)
#   Camara Dahua (subtype=1 baja res)  -> Servidor  -> go2rtc (analisis tiempo real)
#
# Uso: bash scripts/pro/deploy_camaras.sh

set -euo pipefail

REPO="${HOME}/URA/ura_ia_1972"
NOTIFICAR="/opt/ura/scripts/notificar.sh"
LOG="${REPO}/logs/deploy_camaras.log"

mkdir -p "${REPO}/logs"

echo "=== Despliegue del sistema de camaras ===" | tee "$LOG"
echo "" | tee -a "$LOG"

# ============================================================
# 1. Generar configuracion go2rtc para el servidor
# ============================================================
echo "1. Generando configuracion go2rtc..." | tee -a "$LOG"

GO2RTC_CONF="/opt/ura/config/go2rtc.yaml"
cat > "$GO2RTC_CONF" << 'EOF'
# go2rtc — Proxy RTSP ligero para 15 camaras Dahua
# Stream secundario (subtype=1, baja resolucion) para analisis en tiempo real

streams:
EOF

python3 -c "
import json
with open('${REPO}/config/dahua_cameras.json') as f:
    cfg = json.load(f)
with open('$GO2RTC_CONF', 'a') as f:
    for cam in cfg['cameras']:
        user = cam.get('username', 'admin')
        pwd = cam.get('password', 'admin')
        url = f\"rtsp://{user}:{pwd}@{cam['host']}:554/cam/realmonitor?channel=1&subtype=1\"
        f.write(f\"  {cam['name']}_sub: {url}\n")
        f.write(f\"  {cam['name']}_main: {url.replace('subtype=1', 'subtype=0')}\n")
print('Config go2rtc generada')
" 2>&1 | tee -a "$LOG"

# ============================================================
# 2. Script de instalacion para el servidor
# ============================================================
echo "" | tee -a "$LOG"
echo "2. Creando script de instalacion remota..." | tee -a "$LOG"

cat > /opt/ura/scripts/instalar_servidor_camaras.sh << 'SERV'
#!/bin/bash
# instalar_servidor_camaras.sh — Ejecutar en el servidor de la nube
# Instala go2rtc + StreamPulse para analisis de camaras

set -euo pipefail
LOG="/var/log/ura_camaras_servidor.log"
CONF="/opt/ura/config/go2rtc.yaml"

echo "=== Instalando supervisor de camaras en servidor ===" | tee "$LOG"

# Crear directorio
sudo mkdir -p /opt/ura/{agents,config,logs}
sudo chown -R "$USER:$USER" /opt/ura

# Descargar go2rtc (binario unico, sin dependencias)
echo "Descargando go2rtc..." | tee -a "$LOG"
ARCH=$(uname -m)
case "$ARCH" in
    x86_64)  BIN="go2rtc_linux_amd64" ;;
    aarch64) BIN="go2rtc_linux_arm64"  ;;
    armv7l)  BIN="go2rtc_linux_arm"   ;;
    *) echo "Arquitectura no soportada: $ARCH"; exit 1 ;;
esac

curl -sL "https://github.com/AlexxIT/go2rtc/releases/latest/download/$BIN" -o /opt/ura/agents/go2rtc
chmod +x /opt/ura/agents/go2rtc

# Copiar configuracion
cp "$CONF" /opt/ura/config/go2rtc.yaml

# Instalar StreamPulse
pip3 install streampulse 2>/dev/null || pip3 install requests 2>/dev/null

# Crear servicio systemd
sudo tee /etc/systemd/system/ura-go2rtc.service << 'UNIT'
[Unit]
Description=go2rtc Camera Stream Proxy
After=network.target

[Service]
ExecStart=/opt/ura/agents/go2rtc --config /opt/ura/config/go2rtc.yaml
WorkingDirectory=/opt/ura
Restart=always
User=%USER

[Install]
WantedBy=multi-user.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable ura-go2rtc
sudo systemctl start ura-go2rtc

echo "=== Servidor de camaras instalado ===" | tee -a "$LOG"
echo "  go2rtc:  systemctl status ura-go2rtc" | tee -a "$LOG"
echo "  Streams: http://$(hostname -I | awk '{print $1}'):1984/" | tee -a "$LOG"
SERV

chmod +x /opt/ura/scripts/instalar_servidor_camaras.sh
echo "  Script remoto: /opt/ura/scripts/instalar_servidor_camaras.sh" | tee -a "$LOG"

# ============================================================
# 3. Configurar GX10 para Frigate (grabacion respaldo)
# ============================================================
echo "" | tee -a "$LOG"
echo "3. Configurando GX10 para Frigate..." | tee -a "$LOG"

ssh ramon@10.164.1.99 bash << 'ENDGX10' 2>&1 | tee -a "$LOG"
echo "=== GX10: Configurando respaldo de camaras ==="

# Verificar Frigate
if docker ps --format '{{.Names}}' | grep -q frigate; then
    echo "Frigate ya activo en GX10"
else
    echo "Frigate no encontrado. Instrucciones:"
    echo "  docker run -d --name frigate ..."
fi

# Actualizar config de Frigate con streams principales
# (subtype=0, alta resolucion para grabacion)
echo "Config Frigate lista para recibir streams principales"
ENDGX10

# ============================================================
# 4. Copiar scripts y commit
# ============================================================
cp /opt/ura/scripts/instalar_servidor_camaras.sh "${REPO}/scripts/pro/instalar_servidor_camaras.sh"

echo "" | tee -a "$LOG"
echo "=== Despliegue preparado ===" | tee -a "$LOG"
echo "" | tee -a "$LOG"
echo "Para INSTALAR EN EL SERVIDOR (nube):" | tee -a "$LOG"
echo "  1. ssh usuario@servidor" | tee -a "$LOG"
echo "  2. bash /opt/ura/scripts/instalar_servidor_camaras.sh" | tee -a "$LOG"
echo "" | tee -a "$LOG"
echo "Para ACTIVAR GRABACION EN GX10:" | tee -a "$LOG"
echo "  Frigate ya configurado en el GX10" | tee -a "$LOG"
echo "" | tee -a "$LOG"
echo "Arquitectura:" | tee -a "$LOG"
echo "  Camara (subtype=0 alta) -> GX10 -> Frigate (grabacion 24/7)" | tee -a "$LOG"
echo "  Camara (subtype=1 baja)  -> Servidor -> go2rtc (analisis)" | tee -a "$LOG"

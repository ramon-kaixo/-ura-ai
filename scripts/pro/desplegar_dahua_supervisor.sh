#!/bin/bash
# desplegar_dahua_supervisor.sh — Despliega el supervisor de camaras Dahua
# Usa CameraEvents (https://github.com/psyciknz/CameraEvents) via Docker
# Las camaras se supervisan pasivamente via su API HTTP (sin modificar configuracion)

set -e

REPO="${HOME}/URA/ura_ia_1972"
DAHUA_DIR="/opt/ura/agents/dahua"
CONFIG_DIR="/opt/ura/config"
LOG="${HOME}/URA/ura_ia_1972/logs/ura_dahua.log"

echo "=== Desplegando supervisor de camaras Dahua ===" | tee "$LOG"

# 1. Crear configuración de camaras
mkdir -p "$CONFIG_DIR"
if [ ! -f "$CONFIG_DIR/dahua_cameras.json" ]; then
    cat > "$CONFIG_DIR/dahua_cameras.json" << 'EOF'
{
  "cameras": [
    {
      "name": "camara_1",
      "host": "192.168.1.100",
      "port": 80,
      "username": "admin",
      "password": "",
      "events": ["VideoMotion", "CrossLineDetection", "VideoLoss"]
    }
  ],
  "mqtt": {
    "host": "localhost",
    "port": 1883,
    "topic_prefix": "ura/camaras"
  }
}
EOF
    echo "Configuracion creada: $CONFIG_DIR/dahua_cameras.json" | tee -a "$LOG"
    echo "  → EDITA este archivo con las IPs y credenciales reales de tus camaras" | tee -a "$LOG"
fi

# 2. Clonar CameraEvents
if [ ! -d "$DAHUA_DIR" ]; then
    git clone --depth 1 https://github.com/psyciknz/CameraEvents.git "$DAHUA_DIR" 2>&1 | tail -3
fi

# 3. Construir imagen Docker
cd "$DAHUA_DIR"
docker build -t dahua-events . 2>&1 | tail -5

# 4. Iniciar contenedor
docker run -d \
  --name dahua-supervisor \
  --restart unless-stopped \
  --memory="256m" \
  -v "$CONFIG_DIR/dahua_cameras.json:/config/cameras.json:ro" \
  dahua-events 2>&1

echo "=== Dahua supervisor desplegado ===" | tee -a "$LOG"
echo "  Contenedor: dahua-supervisor" | tee -a "$LOG"
echo "  Eventos MQTT: ura/camaras/#" | tee -a "$LOG"

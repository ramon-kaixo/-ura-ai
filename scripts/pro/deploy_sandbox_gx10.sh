#!/bin/bash
# deploy_sandbox_gx10.sh – Despliega la caja de arena (sandbox) en el ASUS GX10
# Ejecutar desde el Mac Mini:
#   bash scripts/pro/deploy_sandbox_gx10.sh
set -e

GX10_IP="${1:-10.164.1.99}"
GX10_USER="${2:-ramon}"

echo "=== Desplegando sandbox URA en GX10 ($GX10_IP) ==="

# 1. Verificar Docker DNS (necesario para builds)
ssh "$GX10_USER@$GX10_IP" bash << 'ENDSSH'
    # Configurar DNS de Docker si no existe
    if [ ! -f /etc/docker/daemon.json ]; then
        sudo tee /etc/docker/daemon.json << 'EOF'
{
  "dns": ["10.164.1.1", "8.8.8.8"],
  "log-driver": "json-file",
  "log-opts": { "max-size": "10m", "max-file": "3" }
}
EOF
        sudo systemctl restart docker
        sleep 5
        echo "Docker DNS configurado"
    fi
ENDSSH

# 2. Copiar y ejecutar script de instalacion
ssh "$GX10_USER@$GX10_IP" 'bash -s' < /opt/ura/scripts/pro/instalar_gx10_circuit.sh 2>/dev/null || true

# 3. Build y arranque de sandboxes
ssh "$GX10_USER@$GX10_IP" bash << 'ENDSSH'
    cd /opt/ura
    echo "Construyendo imagenes sandbox..."
    docker compose -f docker-compose.sandbox.yml build --quiet
    echo "Iniciando contenedores..."
    docker compose -f docker-compose.sandbox.yml up -d
    echo ""
    echo "=== Sandboxes GX10 ==="
    docker ps --filter "name=ura-sandbox" --format "table {{.Names}}\t{{.Status}}"
ENDSSH

echo "=== Despliegue completado ==="

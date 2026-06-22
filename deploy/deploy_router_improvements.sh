#!/bin/bash
# Despliegue de mejoras de robustez para Model Router en ASUS
# Ejecutar en ASUS: bash deploy_router_improvements.sh

set -e

ASUS_DIR="${ASUS_PATH:-/home/ramon/URA}/ura_ia_1972"
DEPLOY_DIR="$ASUS_DIR/deploy"

echo "=== DESPLIEGUE DE MEJORAS DE ROBUSTEZ ==="

# 1. Copiar model-router.service con ExecStartPre
echo "1. Actualizando model-router.service con ExecStartPre..."
sudo cp "$DEPLOY_DIR/model-router.service" /etc/systemd/system/model-router.service
sudo systemctl daemon-reload

# 2. Copiar health check script
echo "2. Instalando health check script..."
sudo cp "$ASUS_DIR/scripts/pro/health_check_router.sh" /usr/local/bin/ura-router-health.sh
sudo chmod +x /usr/local/bin/ura-router-health.sh

# 3. Copiar timer y service de health check
echo "3. Instalando health check timer..."
sudo cp "$DEPLOY_DIR/ura-router-health.timer" /etc/systemd/system/ura-router-health.timer
sudo cp "$DEPLOY_DIR/ura-router-health.service" /etc/systemd/system/ura-router-health.service
sudo systemctl daemon-reload
sudo systemctl enable ura-router-health.timer
sudo systemctl start ura-router-health.timer

# 4. Copiar rate limiter
echo "4. Instalando rate limiter..."
sudo cp "$ASUS_DIR/scripts/pro/router_rate_limiter.py" /usr/local/bin/router_rate_limiter.py

# 5. Copiar alert service
echo "5. Instalando alert service..."
sudo cp "$DEPLOY_DIR/ura-router-alerts.service" /etc/systemd/system/ura-router-alerts.service
sudo systemctl daemon-reload

# 6. Reiniciar model-router.service
echo "6. Reiniciando model-router.service..."
sudo systemctl restart model-router.service

# 7. Verificar estado
echo "7. Verificando estado de servicios..."
echo "--- model-router.service ---"
sudo systemctl status model-router.service --no-pager | head -10
echo "--- ura-router-health.timer ---"
sudo systemctl status ura-router-health.timer --no-pager | head -10

echo "=== DESPLIEGUE COMPLETADO ==="
echo "Mejoras instaladas:"
echo "  ✅ ExecStartPre para prevenir loop de reinicios"
echo "  ✅ Health check automático cada 5 minutos"
echo "  ✅ Rate limiter para prevenir abusos"
echo "  ✅ Alertas systemd para >10 fallos/hora"
echo "  ✅ Cache TTL optimizado a 4 horas"

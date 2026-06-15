#!/bin/bash
set -e
MOTOR_DIR="/opt/motor"
PYTHON="python3"

echo "=== URA Motor de Conocimiento - Instalacion ==="

install -d "$MOTOR_DIR"
cp -r "$(dirname "$(dirname "$0")")"/* "$MOTOR_DIR/"
chmod +x "$MOTOR_DIR/scripts/ura"
ln -sf "$MOTOR_DIR/scripts/ura" /usr/local/bin/ura

$PYTHON -m pip install --quiet psutil qdrant_client 2>/dev/null || true

if command -v apt-get &>/dev/null; then
    apt-get install -y -qq smartmontools lm-sensors 2>/dev/null || true
fi

# Timer systemd unico
cat > /etc/systemd/system/ura-pipeline.service << 'EOF'
[Unit]
Description=URA Motor de Conocimiento - Pipeline completo
After=network.target qdrant.service

[Service]
Type=oneshot
ExecStart=/usr/local/bin/ura pipeline
User=root
StandardOutput=journal
StandardError=journal
EOF

cat > /etc/systemd/system/ura-pipeline.timer << 'EOF'
[Unit]
Description=URA Pipeline cada 5 minutos
Requires=ura-pipeline.service

[Timer]
OnCalendar=*:0/5
Persistent=true

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable --now ura-pipeline.timer || true

echo "OK. ura pipeline cada 5 min activo."
echo "  ura pipeline      # ejecutar ahora"
echo "  ura status        # estado unificado"
echo "  ura check         # preflight"
echo "  ura scan          # solo escanear"
echo "  ura diagnose      # solo diagnosticar"
echo "  ura history       # incidentes Qdrant"
echo "  ura calibrate     # generar baseline"
